from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, TypedDict

from agent.config import Settings
from agent.execute import ExecutionResult, execute_with_fallbacks, save_execution_result
from agent.observe import Observation, capture_observation
from agent.planner import Planner, PlannerResult
from agent.runtime import BrowserRuntime
from agent.security import SecurityDecision, analyze_action, prompt_confirmation
from agent.tracing import TextLogger, TraceLogger, generate_step_id

try:
    from langgraph.graph import END, START, StateGraph
except ImportError as e:  # pragma: no cover
    raise RuntimeError("LangGraph is required for langgraph loop. Install langgraph.") from e


TERMINAL_REASONS = {"goal_satisfied", "goal_failed", "loop_stuck", "budget_exhausted"}
TERMINAL_TYPES = {
    "goal_satisfied": "success",
    "goal_failed": "failure",
    "loop_stuck": "failure",
    "budget_exhausted": "budget",
}
STOP_TO_TERMINAL = {
    "goal_satisfied": "goal_satisfied",
    "progress_auto_done": "goal_satisfied",
    "user_confirm_done": "goal_satisfied",
    "meta_done": "goal_satisfied",
    "progress_ask_user": "goal_failed",
    "meta_ask_user": "goal_failed",
    "planner_timeout": "goal_failed",
    "planner_error": "goal_failed",
    "execute_timeout": "goal_failed",
    "execute_error": "goal_failed",
    "rejected_by_user": "goal_failed",
    "goal_failed": "goal_failed",
    "loop_stuck": "loop_stuck",
    "budget_exhausted": "budget_exhausted",
}
INTERACTIVE_PROMPTS = os.getenv("INTERACTIVE_PROMPTS", "").lower() in {"1", "true", "yes", "on"}


class GraphState(TypedDict, total=False):
    goal: str
    task_mode: str
    goal_kind: str
    goal_stage: str
    session_id: str
    step: int
    observation: Optional[Observation]
    prev_observation: Optional[Observation]
    recent_observations: List[Observation]
    planner_result: Optional[PlannerResult]
    security_decision: Optional[SecurityDecision]
    exec_result: Optional[ExecutionResult]
    stop_reason: Optional[str]
    stop_details: Optional[str]
    repeat_count: int
    stagnation_count: int
    mapping_hash: Optional[int]
    auto_scrolls_used: int
    avoid_elements: List[str]
    visited_urls: Dict[str, int]
    visited_elements: Dict[str, int]
    action_history: List[Dict[str, Any]]
    last_error_context: Optional[str]
    last_progress_score: Optional[int]
    last_progress_evidence: Optional[List[str]]
    records: List[Dict[str, Any]]
    loop_trigger: Optional[str]
    loop_trigger_sig: Optional[tuple[Any, Any, Any]]
    last_state_change: Optional[dict[str, Any]]
    url_changed: Optional[bool]
    dom_changed: Optional[bool]
    exec_fail_counts: Dict[str, int]
    conservative_probe_done: bool
    error_retries: int
    loop_mitigated: bool
    last_action_no_effect: bool
    page_type: Optional[str]
    avoid_actions: List[str]
    candidate_elements: List[Dict[str, Any]]
    candidate_hash: Optional[int]
    prev_candidate_hash: Optional[int]
    artifact_detected: Optional[bool]
    artifact_type: Optional[str]
    progress_steps: int
    no_progress_steps: int
    planner_calls: int
    terminal_reason: Optional[str]
    terminal_type: Optional[str]
    goal_stage: str


def _mapping_hash(obs: Optional[Observation]) -> Optional[int]:
    if not obs:
        return None
    return hash(tuple((el.tag, el.text, el.role) for el in obs.mapping))


def _candidate_hash(candidates: Optional[List[Dict[str, Any]]]) -> Optional[int]:
    if not candidates:
        return None
    try:
        return hash(tuple((c.get("id"), c.get("text"), c.get("role")) for c in candidates))
    except Exception:
        return None


def _goal_tokens(goal: str) -> list[str]:
    return [tok.lower() for tok in goal.replace(",", " ").split() if len(tok) > 3]


def _progress_score(
    goal: str,
    prev_observation: Optional[Observation],
    current_observation: Observation,
    last_action: Dict[str, Any],
    keywords: List[str],
) -> tuple[int, list[str], bool, bool, int]:
    evidence: list[str] = []
    score = 0

    goal_tokens = _goal_tokens(goal)
    prev_url = prev_observation.url if prev_observation else ""
    url_changed = bool(prev_observation and prev_url != current_observation.url)
    if url_changed:
        score += 1
        evidence.append(f"url_changed:{prev_url} -> {current_observation.url}")

    url_lower = current_observation.url.lower()
    url_hits = [kw for kw in keywords if kw in url_lower]
    if url_hits:
        score += 1
        evidence.append(f"url_keywords:{url_hits}")

    mapping_text = " ".join((el.text or "") + " " + (el.role or "") for el in current_observation.mapping).lower()
    map_hits = [kw for kw in keywords if kw in mapping_text]
    if map_hits:
        score += 1
        evidence.append(f"mapping_keywords:{map_hits}")

    goal_hits = [tok for tok in goal_tokens if tok in mapping_text or tok in url_lower]
    if goal_hits:
        score += 1
        evidence.append(f"goal_hits:{goal_hits}")

    mapping_goal_hits_count = sum(1 for tok in goal_tokens if tok in mapping_text)

    detail_confidence = False
    title_lower = current_observation.title.lower()
    title_hits = [tok for tok in goal_tokens if tok in title_lower]
    if title_hits and len(title_hits) >= max(1, len(goal_tokens) // 2):
        detail_confidence = True
        evidence.append(f"title_hits:{title_hits}")
        score += 1

    path_hits = [tok for tok in goal_tokens if tok in url_lower]
    if path_hits and len(path_hits) >= max(1, len(goal_tokens) // 2):
        detail_confidence = True
        evidence.append(f"url_path_hits:{path_hits}")
        score += 1

    if last_action.get("element_id") is not None and prev_observation:
        target_id = last_action.get("element_id")
        element_text = ""
        for el in prev_observation.mapping:
            if el.id == target_id:
                element_text = (el.text or "") + " " + (el.role or "")
                break
        el_lower = element_text.lower()
        el_hits = [kw for kw in keywords if kw in el_lower]
        if el_hits:
            score += 1
            evidence.append(f"last_action_target_hits:{el_hits}")

    # Heuristic listing/detail: many links/buttons vs single dense content.
    links = sum(1 for m in current_observation.mapping if (m.role or "").lower() in {"link", "button"} or m.tag in {"a", "button"})
    inputs = sum(1 for m in current_observation.mapping if m.tag in {"input", "textarea", "select"})
    listing_score = links + inputs
    detail_score = len([m for m in current_observation.mapping if len((m.text or "")) > 40])

    return score, evidence, url_changed, detail_confidence, mapping_goal_hits_count, listing_score, detail_score


def _goal_is_find_only(goal: str) -> bool:
    goal_low = goal.lower()
    download_verbs = ["download", "скачай", "скачать", "add to cart", "добавь", "купить", "закажи", "оформи"]
    return not any(v in goal_low for v in download_verbs)


def _classify_task_mode(goal: str) -> str:
    goal_low = goal.lower()
    if any(k in goal_low for k in ["найди", "ищи", "find", "search", "достань", "добыть"]):
        return "find"
    if any(k in goal_low for k in ["ответ", "поясни", "explain", "answer"]):
        return "answer"
    if any(k in goal_low for k in ["скачай", "download"]):
        return "download"
    return "browse"


def _page_type_from_scores(listing_score: int, detail_score: int, detail_confidence: bool) -> str:
    if detail_confidence:
        return "detail"
    if listing_score > detail_score + 2:
        return "listing"
    return "unknown"


def _extract_candidates(mapping: List[Any], goal_tokens: List[str], limit: int = 10) -> List[Dict[str, Any]]:
    scored: List[tuple[int, Any]] = []
    for el in mapping:
        text = (getattr(el, "text", "") or "").lower()
        role = (getattr(el, "role", "") or "").lower()
        tag = (getattr(el, "tag", "") or "").lower()
        score = 0
        for tok in goal_tokens:
            if tok in text:
                score += 2
            elif tok in role or tok in tag:
                score += 1
        if score > 0:
            scored.append((score, el))
    scored.sort(key=lambda x: x[0], reverse=True)
    result: List[Dict[str, Any]] = []
    for score, el in scored[:limit]:
        result.append(
            {
                "id": el.id,
                "text": el.text,
                "role": el.role,
                "score": score,
                "zone": el.zone,
                "is_nav": getattr(el, "is_nav", False),
                "is_disabled": getattr(el, "is_disabled", False),
            }
        )
    return result


# Action confidence scoring for obvious UI affordances.
ACTION_WORDS: Dict[str, int] = {
    "+": 5,
    "add": 4,
    "add to cart": 5,
    "cart": 4,
    "basket": 4,
    "в корзину": 5,
    "купить": 5,
    "заказать": 4,
    "добавить": 4,
}
DANGER_WORDS = {"delete", "remove", "cancel", "отмена", "удалить"}


def _score_action_candidate(candidate: Dict[str, Any], observation: Observation, state: GraphState) -> int:
    score = 0
    text = (candidate.get("text") or "").lower()
    role = (candidate.get("role") or "").lower()
    score += int(candidate.get("score") or 0)
    for word, bonus in ACTION_WORDS.items():
        if word in text:
            score += bonus
    if role == "button":
        score += 3
    elif role == "link":
        score += 1
    el = next((m for m in observation.mapping if m.id == candidate.get("id")), None)
    if el:
        if getattr(el, "is_disabled", False):
            return -999
        area = el.bbox.width * el.bbox.height
        if area > 800:
            score += 2
        if el.zone == 0:
            score += 2
    seen_count = state.get("visited_elements", {}).get(str(candidate.get("id")), 0)
    if seen_count >= 2:
        score += 2
    for word in DANGER_WORDS:
        if word in text:
            score -= 10
    # Penalize nav/footer/secondary UI zones
    if candidate.get("is_nav"):
        score -= 5
    zone = candidate.get("zone")
    if zone is not None and zone > 2:  # lower zones treated as footer-ish
        score -= 2
    # Penalize cart/basket secondary UI
    if any(w in text for w in ["cart", "basket", "корзина"]):
        score -= 3
    return score


def _pick_committed_action(candidates: List[Dict[str, Any]], observation: Observation, state: GraphState, threshold: int = 8) -> Optional[Dict[str, Any]]:
    if not candidates:
        return None
    scored = [(_score_action_candidate(c, observation, state), c) for c in candidates]
    scored.sort(key=lambda x: x[0], reverse=True)
    best_score, best = scored[0]
    # commit window: if same candidate appeared several times, boost
    seen_count = state.get("visited_elements", {}).get(str(best.get("id")), 0)
    if seen_count >= 2:
        best_score += 2
    if best_score >= threshold:
        return {
            "tool": "browser_action",
            "action": "click",
            "element_id": best["id"],
            "value": None,
            "requires_confirmation": False,
            "reason": f"commit_high_confidence={best_score}",
        }
    return None


def _classify_goal_kind(goal: str) -> str:
    gl = goal.lower()
    if any(k in gl for k in ["список", "list", "перевод", "translations", "translations", "results"]):
        return "list"
    if any(k in gl for k in ["добавь", "добавить", "купи", "в корзину", "buy", "add to cart", "order", "закажи"]):
        return "action"
    return "object"


def _stage_rank(stage: str) -> int:
    order = ["orient", "context", "locate", "verify", "done"]
    return order.index(stage) if stage in order else 0


def _promote_stage(current: str, proposed: str) -> str:
    return proposed if _stage_rank(proposed) > _stage_rank(current) else current


def _goal_checker(
    state: GraphState,
    observation: Observation,
    *,
    goal_tokens: List[str],
    page_type: str,
    listing_score: int,
    detail_score: int,
    detail_confidence: bool,
    no_progress_steps: int,
    max_no_progress_steps: int,
    planner_calls: int,
    max_planner_calls: int,
) -> tuple[str, bool, str, List[str], bool, bool, str]:
    stage = state.get("goal_stage", "orient")
    goal_kind = state.get("goal_kind", "object")
    evidence: List[str] = []
    artifact_detected = False
    artifact_type = "none"

    url_title = (observation.url + " " + observation.title).lower()
    goal_hit_url_title = any(tok in url_title for tok in goal_tokens if tok)
    mapping_text = " ".join((m.text or "") for m in observation.mapping).lower()
    mapping_goal_hits = sum(1 for tok in goal_tokens if tok in mapping_text)

    # Stage promotion
    if goal_hit_url_title or mapping_goal_hits > 0:
        stage = _promote_stage(stage, "context")
    if page_type == "listing" and mapping_goal_hits > 0:
        stage = _promote_stage(stage, "locate")
    if page_type == "detail" and goal_hit_url_title:
        stage = _promote_stage(stage, "verify")

    # Artifact detection by goal_kind
    if goal_kind == "object":
        # Detail URL heuristics take precedence for objects.
        detail_url_hit = "/vault/" in observation.url or any(ch.isdigit() for ch in observation.url.split("/")[-1])
        if detail_url_hit and goal_hit_url_title:
            artifact_detected = True
            artifact_type = "detail"
            evidence.append("object_detail_url")
            stage = _promote_stage(stage, "verify")
        elif (page_type == "detail" and goal_hit_url_title) or (
            goal_hit_url_title and mapping_goal_hits >= 1 and (len(observation.mapping) <= max(15, 5))
        ):
            artifact_detected = True
            artifact_type = "detail"
            evidence.append("object_detail")
    elif goal_kind == "list":
        if page_type == "listing" and mapping_goal_hits >= 1 and listing_score > detail_score:
            artifact_detected = True
            artifact_type = "list"
            evidence.append("list_results")
    elif goal_kind == "action":
        if goal_hit_url_title and mapping_goal_hits >= 1:
            artifact_detected = True
            artifact_type = "action"
            evidence.append("action_context")

    fulfilled = artifact_detected and stage in {"verify", "locate"} if goal_kind == "list" else artifact_detected and stage in {"verify"}
    if goal_kind == "action" and artifact_detected:
        fulfilled = False  # действие ещё не совершено; здесь только контекст

    failed = False
    fail_reason = ""
    # Failure if exhausted steps without progress and stage not advanced.
    if not artifact_detected and no_progress_steps >= max_no_progress_steps and stage in {"orient", "context"}:
        failed = True
        fail_reason = f"insufficient_knowledge:no_progress_steps={no_progress_steps}"
    if not artifact_detected and planner_calls >= max_planner_calls:
        failed = True
        fail_reason = f"llm_budget_exhausted:planner_calls={planner_calls}"

    return stage, fulfilled, artifact_type, evidence, artifact_detected, failed, fail_reason


async def _capture_with_retry(
    runtime: BrowserRuntime,
    settings: Settings,
    *,
    viewports: int = 1,
    label: Optional[str] = None,
    capture_screenshot: Optional[bool] = None,
    max_elements: Optional[int] = None,
) -> Observation:
    page = await runtime.ensure_page()
    try:
        setattr(page, "_hide_overlay", settings.hide_overlay)
        return await capture_observation(
            page,
            settings,
            viewports=viewports,
            label=label,
            capture_screenshot=capture_screenshot,
            max_elements=max_elements,
        )
    except Exception as exc:
        msg = str(exc).lower()
        # Retry once on TargetClosed or navigation/context issues during evaluate.
        if not (runtime.is_target_closed_error(exc) or "execution context was destroyed" in msg or "context was destroyed" in msg or "frame was detached" in msg):
            raise
        page = await runtime.ensure_page()
        try:
            await asyncio.sleep(0.2)
        except Exception:
            pass
        setattr(page, "_hide_overlay", settings.hide_overlay)
        return await capture_observation(
            page,
            settings,
            viewports=viewports,
            label=label,
            capture_screenshot=capture_screenshot,
            max_elements=max_elements,
        )


async def _paged_scan(runtime: BrowserRuntime, settings: Settings, *, label_prefix: Optional[str] = None) -> Observation:
    combined_mapping: list = []
    last_obs: Optional[Observation] = None
    steps = max(1, settings.paged_scan_steps)
    viewports = max(1, settings.paged_scan_viewports)
    for i in range(steps):
        obs = await _capture_with_retry(
            runtime,
            settings,
            viewports=viewports,
            label=f"{label_prefix}-scan{i}" if label_prefix else None,
        )
        combined_mapping.extend(obs.mapping)
        last_obs = obs
        if i < steps - 1:
            try:
                page = await runtime.ensure_page()
                await page.mouse.wheel(0, 350)
            except Exception:
                pass

    if not last_obs:
        return await _capture_with_retry(
            runtime,
            settings,
            viewports=viewports,
            label=label_prefix,
        )

    seen = set()
    deduped = []
    for m in combined_mapping:
        key = (m.tag, m.text, m.role, int(m.bbox.x), int(m.bbox.y), int(m.bbox.width), int(m.bbox.height))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(m)

    return Observation(
        url=last_obs.url,
        title=last_obs.title,
        mapping=sorted(deduped, key=lambda m: (m.bbox.y, m.bbox.x)),
        screenshot_path=last_obs.screenshot_path,
        recorded_at=last_obs.recorded_at,
    )


def build_graph(
    settings: Settings,
    planner: Planner,
    runtime: BrowserRuntime,
    execute_enabled: bool,
    text_log: Optional[TextLogger] = None,
    trace: Optional[TraceLogger] = None,
):
    if text_log is None:
        class _NullLog:
            def write(self, *_: Any, **__: Any) -> None:
                return None
        text_log = _NullLog()  # type: ignore[assignment]
    workflow = StateGraph(GraphState)
    graph_config = {"recursion_limit": max(settings.max_steps + 20, 50)}

    async def observe_node(state: GraphState) -> GraphState:
        # Hard guard: limit check handled in run/goal_check; no stop here.
        page = await runtime.ensure_page()
        # Pass overlay/mapping limit hints via page attributes
        setattr(page, "_hide_overlay", settings.hide_overlay)
        setattr(page, "_mapping_boost", 0)
        # Switch active page by hint if tab changed (new page created)
        if state.get("planner_result") and state["planner_result"].action.get("action") == "switch_tab":
            hint_val = state["planner_result"].action.get("value")
            if hint_val:
                await runtime.set_active_page_by_hint(url_substr=str(hint_val), title_substr=str(hint_val))
        observation = await _capture_with_retry(
            runtime,
            settings,
            capture_screenshot=False,
            label=f"{state['session_id']}-step{state.get('step', 0)}",
        )
        # If mapping looks sparse on a listing-like page, do a couple of reobserves with small waits to catch lazy/virtualized items.
        list_like = False
        _, _, _, detail_confidence_tmp, _, listing_score_tmp, detail_score_tmp = _progress_score(
            state["goal"], state.get("prev_observation"), observation, {}, [kw.lower() for kw in settings.progress_keywords]
        )
        list_like = listing_score_tmp > detail_score_tmp and not detail_confidence_tmp
        if list_like and len(observation.mapping) < max(5, int(settings.mapping_limit * 0.5)):
            merged = list(observation.mapping)
            for _ in range(2):
                try:
                    await asyncio.sleep(0.3)
                except Exception:
                    pass
                extra = await _capture_with_retry(
                    runtime,
                    settings,
                    capture_screenshot=False,
                    label=f"{state['session_id']}-step{state.get('step', 0)}-retry",
                )
                merged.extend(extra.mapping)
            # dedupe by (tag,text,role,bbox)
            seen = set()
            unique = []
            for m in merged:
                key = (m.tag, m.text, m.role, int(m.bbox.x), int(m.bbox.y), int(m.bbox.width), int(m.bbox.height))
                if key in seen:
                    continue
                seen.add(key)
                unique.append(m)
            observation = Observation(
                url=observation.url,
                title=observation.title,
                mapping=sorted(unique, key=lambda m: (m.bbox.y, m.bbox.x)),
                screenshot_path=observation.screenshot_path,
                recorded_at=observation.recorded_at,
            )

        repeat_count = state.get("repeat_count", 0)
        stagnation = state.get("stagnation_count", 0)
        mapping_hash_prev = state.get("mapping_hash")
        mapping_hash_curr = _mapping_hash(observation)
        if mapping_hash_prev is not None and mapping_hash_prev == mapping_hash_curr:
            stagnation += 1
        else:
            stagnation = 0

        loop_detected = repeat_count >= settings.loop_repeat_threshold or stagnation >= settings.stagnation_threshold
        auto_scrolls_used = state.get("auto_scrolls_used", 0)
        recent = list(state.get("recent_observations", []))
        recent.append(observation)
        recent = recent[-3:]
        goal_tokens = _goal_tokens(state["goal"])
        candidates = _extract_candidates(observation.mapping, goal_tokens, limit=10)

        # Goal satisfaction quick check: URL/title contains goal tokens AND mapping has hits or listing shrunk.
        url_title = (observation.url + " " + observation.title).lower()
        goal_hit_url_title = any(tok in url_title for tok in goal_tokens if tok)
        mapping_text = " ".join((m.text or "") for m in observation.mapping).lower()
        mapping_goal_hits = sum(1 for tok in goal_tokens if tok in mapping_text)
        goal_satisfied = False
        evidence: List[str] = []
        goal_kind = state.get("goal_kind", "object")
        # Very conservative: only satisfy if object goal and clear hit on URL/title and small mapping (detail-ish).
        if goal_kind == "object" and goal_hit_url_title and (mapping_goal_hits >= 1 and len(observation.mapping) <= max(15, settings.mapping_limit // 2)):
            goal_satisfied = True
            evidence.append("goal_tokens_in_url_title")
            evidence.append(f"mapping_hits={mapping_goal_hits}")

        new_state = {
            **state,
            "prev_observation": state.get("observation"),
            "observation": observation,
            "mapping_hash": mapping_hash_curr,
            "stagnation_count": stagnation,
            "auto_scrolls_used": auto_scrolls_used,
            "loop_trigger": "loop" if loop_detected else None,
            "recent_observations": recent,
            "loop_mitigated": False,
            "candidate_elements": candidates,
            "prev_candidate_hash": state.get("candidate_hash"),
            "candidate_hash": _candidate_hash(candidates),
        }
        if goal_satisfied:
            new_state["stop_reason"] = "goal_satisfied"
            new_state["stop_details"] = ";".join(evidence)
            return new_state
        return new_state

    async def loop_mitigation_node(state: GraphState) -> GraphState:
        if not state.get("loop_trigger"):
            return state
        page = await runtime.ensure_page()
        setattr(page, "_mapping_boost", settings.loop_retry_mapping_boost)
        auto_scrolls_used = state.get("auto_scrolls_used", 0)
        conservative_done = state.get("conservative_probe_done", False)
        if settings.conservative_observe and not conservative_done:
            text_log.write(f"[{state['session_id']}] loop mitigation: conservative observe before scroll")
            if trace:
                try:
                    trace.write(
                        {
                            "step": state.get("step", 0),
                            "session_id": state["session_id"],
                            "node": "loop_mitigation",
                            "action": "conservative_pass",
                            "loop_trigger": state.get("loop_trigger"),
                        }
                    )
                except Exception:
                    pass
            return {**state, "conservative_probe_done": True}
        if auto_scrolls_used < settings.max_auto_scrolls:
            text_log.write(f"[{state['session_id']}] loop mitigation: paged scan")
            observation = await _paged_scan(runtime, settings, label_prefix=state["session_id"])
            recent = list(state.get("recent_observations", []))
            recent.append(observation)
            recent = recent[-3:]
            return {
                **state,
                "observation": observation,
                "prev_observation": state.get("observation"),
                "mapping_hash": _mapping_hash(observation),
                "auto_scrolls_used": auto_scrolls_used + 1,
                "stagnation_count": 0,
                "loop_mitigated": True,
                "recent_observations": recent,
            }
        if trace:
            try:
                trace.write(
                    {
                        "step": state.get("step", 0),
                        "session_id": state["session_id"],
                        "node": "loop_mitigation",
                        "action": "paged_scan_limit_reached",
                        "loop_trigger": state.get("loop_trigger"),
                    }
                )
            except Exception:
                pass
        return {**state, "loop_mitigated": True}

    async def goal_check_node(state: GraphState) -> GraphState:
        observation = state["observation"]
        if observation is None:
            return state
        prev_observation = state.get("prev_observation")
        last_action = state.get("planner_result").action if state.get("planner_result") else (state.get("action_history", [])[-1] if state.get("action_history") else {})
        # Budget guard by max_steps to avoid runaway before recursion_limit.
        if state.get("step", 0) >= settings.max_steps:
            return {
                **state,
                "stop_reason": "budget_exhausted",
                "stop_details": f"max_steps={settings.max_steps}",
                "terminal_reason": "budget_exhausted",
                "terminal_type": TERMINAL_TYPES.get("budget_exhausted"),
            }
        score_ctx = _progress_score(
            state["goal"],
            prev_observation,
            observation,
            last_action or {},
            [kw.lower() for kw in settings.progress_keywords],
        )
        (_, _, _, detail_confidence, _, listing_score, detail_score) = score_ctx
        page_type = _page_type_from_scores(listing_score, detail_score, detail_confidence)
        goal_stage, fulfilled, artifact_type, goal_evidence, artifact_detected, failed, fail_reason = _goal_checker(
            state,
            observation,
            goal_tokens=_goal_tokens(state["goal"]),
            page_type=page_type,
            listing_score=listing_score,
            detail_score=detail_score,
            detail_confidence=detail_confidence,
            no_progress_steps=state.get("no_progress_steps", 0),
            max_no_progress_steps=settings.max_no_progress_steps,
            planner_calls=state.get("planner_calls", 0),
            max_planner_calls=settings.max_planner_calls,
        )
        # If we spent a reasonable budget but never left orient/context, treat as insufficient knowledge.
        stage_not_advanced = (
            not artifact_detected
            and goal_stage in {"orient", "context"}
            and state.get("planner_calls", 0) >= max(2, settings.max_planner_calls // 2)
            and state.get("step", 0) >= max(3, settings.max_steps // 2)
        )
        if stage_not_advanced and not failed:
            failed = True
            fail_reason = f"insufficient_knowledge:stage_not_advanced stage={goal_stage} planner_calls={state.get('planner_calls', 0)} step={state.get('step', 0)}"
        # Loop/no-progress detection: if stagnation and no artifact.
        repeat = state.get("repeat_count", 0)
        stagnation = state.get("stagnation_count", 0)
        auto_scrolls = state.get("auto_scrolls_used", 0)
        url_same = bool(prev_observation and prev_observation.url == observation.url)
        dom_same = bool(_mapping_hash(prev_observation) == _mapping_hash(observation)) if prev_observation else False
        candidates_same = bool(state.get("prev_candidate_hash") is not None and state.get("prev_candidate_hash") == state.get("candidate_hash"))
        no_progress_budget = state.get("no_progress_steps", 0) >= settings.max_no_progress_steps
        counters_exhausted = (
            repeat >= settings.loop_repeat_threshold
            and stagnation >= settings.stagnation_threshold
            and auto_scrolls >= settings.max_auto_scrolls
        )
        world_frozen = url_same and dom_same and candidates_same
        no_progress = not artifact_detected and (
            (world_frozen and no_progress_budget)
            or (world_frozen and counters_exhausted)
            or (no_progress_budget and counters_exhausted)
        )
        if fulfilled and state.get("goal_kind", "object") != "action":
            return {
                **state,
                "goal_stage": goal_stage,
                "artifact_detected": artifact_detected,
                "artifact_type": artifact_type,
                "page_type": page_type,
                "stop_reason": "goal_satisfied",
                "stop_details": ";".join(goal_evidence) if goal_evidence else artifact_type,
                "terminal_reason": "goal_satisfied",
                "terminal_type": TERMINAL_TYPES.get("goal_satisfied"),
            }
        if failed:
            return {
                **state,
                "goal_stage": goal_stage,
                "artifact_detected": artifact_detected,
                "artifact_type": artifact_type,
                "page_type": page_type,
                "stop_reason": "goal_failed",
                "stop_details": fail_reason,
                "terminal_reason": "goal_failed",
                "terminal_type": TERMINAL_TYPES.get("goal_failed"),
        }
        if no_progress:
            return {
                **state,
                "goal_stage": goal_stage,
                "artifact_detected": artifact_detected,
                "artifact_type": artifact_type,
                "page_type": page_type,
                "stop_reason": "loop_stuck",
                "stop_details": f"repeat={repeat},stagnation={stagnation},auto_scrolls={auto_scrolls},url_same={url_same},dom_same={dom_same},candidates_same={candidates_same}",
                "terminal_reason": "loop_stuck",
                "terminal_type": TERMINAL_TYPES.get("loop_stuck"),
            }
        return {
            **state,
            "goal_stage": goal_stage,
            "artifact_detected": artifact_detected,
            "artifact_type": artifact_type,
            "page_type": page_type,
        }

    async def planner_node(state: GraphState) -> GraphState:
        observation = state["observation"]
        if observation is None:
            raise RuntimeError("Planner node missing observation")
        loop_detected = bool(state.get("loop_trigger"))
        # FSM / goal kind
        goal_kind = state.get("goal_kind", "object")
        goal_stage = state.get("goal_stage", "orient")
        # Detect listing/detail to steer the planner toward exploration.
        prev_observation = state.get("prev_observation")
        last_action = state.get("planner_result").action if state.get("planner_result") else (state.get("action_history", [])[-1] if state.get("action_history") else {})
        score_ctx = _progress_score(
            state["goal"],
            prev_observation,
            observation,
            last_action or {},
            [kw.lower() for kw in settings.progress_keywords],
        )
        (_, _, _, detail_confidence, _, listing_score, detail_score) = score_ctx
        listing_detected = listing_score > detail_score and not detail_confidence
        page_type = _page_type_from_scores(listing_score, detail_score, detail_confidence)
        explore_mode = _goal_is_find_only(state["goal"]) or _classify_task_mode(state["goal"]) == "find"
        mapping_limit = settings.mapping_limit + settings.loop_retry_mapping_boost if loop_detected else settings.mapping_limit
        error_context = state.get("last_error_context") or "none"
        include_screenshot = len(observation.mapping) <= max(10, int(settings.mapping_limit * 0.5))
        if error_context != "none":
            include_screenshot = True
        if include_screenshot and not observation.screenshot_path:
            # recapture with screenshot
            observation = await _capture_with_retry(
                runtime,
                settings,
                max_elements=len(observation.mapping),
                viewports=settings.paged_scan_viewports,
                capture_screenshot=True,
                label=f"{state['session_id']}-step{state.get('step', 0)}-shot",
            )
        progress_context_parts = [f"keywords={settings.progress_keywords}", f"listing_detected={listing_detected}"]
        # Mark if previous search did not change page to encourage strategy shift.
        search_no_change = False
        state_change = state.get("last_state_change") or {}
        state_change_hint = (
            f"url={observation.url}; url_changed={state_change.get('url_changed')} dom_changed={state_change.get('dom_changed')}"
        )
        if last_action and last_action.get("action") == "search" and not state_change.get("url_changed") and not state_change.get("dom_changed"):
            search_no_change = True
            progress_context_parts.append("search_no_change=True")
        # Avoid repeating same action on same URL without effect.
        avoid_actions: List[str] = list(state.get("avoid_actions", []))
        loop_sig = state.get("loop_trigger_sig")
        if loop_sig and loop_sig[0] == "search" and state.get("repeat_count", 0) >= 1:
            avoid_actions.append("search")
            progress_context_parts.append("avoid_search_due_to_loop=True")
        if state.get("last_action_no_effect"):
            progress_context_parts.append("last_action_no_effect=True")
        # Detect presence of a search control on the page; if listing and search is available, discourage navigation before using it.
        search_controls: List[int] = []
        for m in observation.mapping:
            role = (getattr(m, "role", "") or "").lower()
            tag = (getattr(m, "tag", "") or "").lower()
            txt = (getattr(m, "text", "") or "").lower()
            attr_name = (getattr(m, "attr_name", "") or "").lower() if getattr(m, "attr_name", None) else ""
            attr_id = (getattr(m, "attr_id", "") or "").lower() if getattr(m, "attr_id", None) else ""
            aria_label = (getattr(m, "aria_label", "") or "").lower() if getattr(m, "aria_label", None) else ""
            if role in {"searchbox"} or tag == "input" or tag == "textarea":
                if "search" in txt or "search" in attr_name or "search" in attr_id or "search" in aria_label:
                    search_controls.append(m.id)
        search_available = bool(search_controls)
        if listing_detected and search_available and state.get("repeat_count", 0) >= 0:
            avoid_actions.append("navigate")
            progress_context_parts.append(f"search_available={search_controls}")
        actions_context = "; ".join(
            f"{a.get('action')} el={a.get('element_id')} url_changed={a.get('url_changed')} dom_changed={a.get('dom_changed')}"
            for a in state.get("action_history", [])[-5:]
        ) or "none"
        loop_context = f"loop_trigger={state.get('loop_trigger')} auto_scrolls_used={state.get('auto_scrolls_used')} avoid={state.get('avoid_elements')} max_attempts_per_element={settings.max_attempts_per_element}"
        fail_counts = state.get("exec_fail_counts", {})
        attempts_context = f"fail_counts={fail_counts}"
        base_limit = settings.mapping_limit
        # Dynamic mapping limit: boost for longer goals or after errors, cap at 150.
        goal_len = len(state["goal"]) if state.get("goal") else 0
        dynamic_limit = base_limit + (10 if goal_len > 120 else 0) + (settings.loop_retry_mapping_boost if error_context != "none" else 0)
        mapping_limit = min(150, dynamic_limit)
        # FSM allowed actions guidance.
        allowed_actions = ["click", "scroll", "navigate", "search", "go_back", "go_forward", "switch_tab"]
        if goal_stage in {"context"}:
            allowed_actions = ["click", "scroll", "search", "go_back"]
        elif goal_stage in {"locate"}:
            allowed_actions = ["click", "scroll", "search", "go_back", "navigate"]
        elif goal_stage in {"verify"}:
            allowed_actions = ["click", "scroll", "screenshot", "go_back"]
        # Meta actions allowed only from locate/verify onward.
        allowed_meta = ["done", "ask_user"] if goal_stage in {"locate", "verify"} else []
        allowed_actions_meta = allowed_actions + allowed_meta
        progress_context = "; ".join(progress_context_parts + [f"allowed_actions={allowed_actions}"])
        # Try high-confidence commit (skip planner) if obvious action present.
        commit_action = _pick_committed_action(state.get("candidate_elements", []), observation, state)
        if commit_action:
            return {
                **state,
                "planner_result": PlannerResult(action=commit_action, raw_response={}, retries_used=0),
                "goal_stage": goal_stage,
                "terminal_reason": None,
            }
        try:
            planner_result = await asyncio.wait_for(
                planner.plan(
                    goal=state["goal"],
                    observation=observation,
                    recent_observations=state.get("recent_observations", []),
                    include_screenshot=include_screenshot,
                    mapping_limit=mapping_limit,
                    max_retries=2,
                    raw_log_dir=settings.paths.state_dir if settings.enable_raw_logs else None,
                    step_id=f"{state['session_id']}-step{state.get('step', 0)}",
                    loop_flag=loop_detected,
                    loop_exhausted=loop_detected and state.get("auto_scrolls_used", 0) >= settings.max_auto_scrolls,
                    avoid_elements=state.get("avoid_elements", []),
                    error_context=error_context,
                    progress_context=progress_context,
                    actions_context=actions_context + f"; {loop_context}; {attempts_context}",
                    listing_detected=listing_detected,
                    explore_mode=explore_mode,
                    avoid_search="search" in avoid_actions,
                    search_no_change=search_no_change,
                    page_type=page_type,
                    task_mode=_classify_task_mode(state["goal"]),
                    avoid_actions=avoid_actions,
                    candidate_elements=state.get("candidate_elements", []),
                    search_controls=search_controls,
                    state_change_hint=state_change_hint,
                    allowed_actions=allowed_actions,
                ),
                timeout=settings.planner_timeout_sec,
            )
            # increment planner call budget
            state["planner_calls"] = state.get("planner_calls", 0) + (1 + planner_result.retries_used)
            action_type = planner_result.action.get("action")
            if action_type not in allowed_actions_meta:
                state["stop_reason"] = "planner_disallowed_action"
                state["stop_details"] = f"action={action_type}; allowed={allowed_actions_meta}"
                if trace:
                    try:
                        trace.write(
                            {
                                "step": state.get("step", 0),
                                "session_id": state["session_id"],
                                "node": "planner",
                                "stop_reason": state["stop_reason"],
                                "stop_details": state["stop_details"],
                            }
                        )
                    except Exception:
                        pass
                return state
        except asyncio.TimeoutError:
            text_log.write(f"[{state['session_id']}] planner timeout at step={state.get('step', 0)}; stopping")
            records = state.get("records", [])
            planner_record = {
                "step": state.get("step", 0),
                "session_id": state["session_id"],
                "step_id": f"{state['session_id']}-step{state.get('step', 0)}",
                "action": {"action": "planner_timeout"},
                "planner_retries": 0,
                "security_requires_confirmation": False,
                "execute_success": None,
                "execute_error": "planner timeout",
                "exec_result_path": None,
                "planner_raw_path": None,
                "loop_trigger": state.get("loop_trigger"),
                "stop_reason": "planner_timeout",
                "stop_details": f"step={state.get('step', 0)}",
                "loop_trigger_sig": state.get("loop_trigger_sig"),
                "attempts_per_element": state.get("exec_fail_counts", {}),
            }
            records.append(planner_record)
            if trace:
                try:
                    trace.write(planner_record)
                except Exception:
                    pass
            return {
                **state,
                "records": records,
                "observation": observation,
                "stop_reason": "planner_timeout",
                "stop_details": f"step={state.get('step', 0)}",
            }
        except Exception as exc:
            text_log.write(f"[{state['session_id']}] planner error at step={state.get('step', 0)}: {exc}")
            records = state.get("records", [])
            planner_record = {
                "step": state.get("step", 0),
                "session_id": state["session_id"],
                "step_id": f"{state['session_id']}-step{state.get('step', 0)}",
                "action": {"action": "planner_error"},
                "planner_retries": 0,
                "security_requires_confirmation": False,
                "execute_success": None,
                "execute_error": str(exc),
                "exec_result_path": None,
                "planner_raw_path": None,
                "loop_trigger": state.get("loop_trigger"),
                "stop_reason": "planner_error",
                "stop_details": str(exc),
                "loop_trigger_sig": state.get("loop_trigger_sig"),
                "attempts_per_element": state.get("exec_fail_counts", {}),
            }
            records.append(planner_record)
            if trace:
                try:
                    trace.write(planner_record)
                except Exception:
                    pass
            return {
                **state,
                "records": records,
                "observation": observation,
                "stop_reason": "planner_error",
                "stop_details": str(exc),
            }
        return {**state, "observation": observation, "planner_result": planner_result}

    async def safety_node(state: GraphState) -> GraphState:
        observation = state["observation"]
        planner_result = state["planner_result"]
        if observation is None or planner_result is None:
            raise RuntimeError("Safety node missing observation or planner result")
        decision = analyze_action(planner_result.action, observation)
        return {**state, "security_decision": decision}

    async def confirm_node(state: GraphState) -> GraphState:
        decision = state["security_decision"]
        planner_result = state["planner_result"]
        if not decision or not planner_result:
            raise RuntimeError("Confirm node missing data")
        allowed = prompt_confirmation(planner_result.action, decision.reason, auto_confirm=settings.auto_confirm)
        if not allowed:
            return {**state, "stop_reason": "rejected_by_user", "stop_details": decision.reason or "rejected"}
        return state

    async def execute_node(state: GraphState) -> GraphState:
        observation = state["observation"]
        planner_result = state["planner_result"]
        if observation is None or planner_result is None:
            raise RuntimeError("Execute node missing observation or planner result")

        action = planner_result.action
        step_id = generate_step_id(f"{state['session_id']}-step{state.get('step', 0)}")
        exec_result_path = None
        exec_result: Optional[ExecutionResult] = None
        exec_success: Optional[bool] = None
        exec_error: Optional[str] = None
        new_obs = observation
        obs_before = observation

        # Meta actions: stop immediately with reason (navigate executes normally).
        if action.get("action") in {"done", "ask_user"}:
            if state.get("goal_stage") in {"orient", "context"}:
                records = state.get("records", [])
                record = {
                    "step": state.get("step", 0),
                    "session_id": state["session_id"],
                    "step_id": step_id,
                    "action": action,
                    "planner_retries": planner_result.retries_used if planner_result else 0,
                    "security_requires_confirmation": state.get("security_decision").requires_confirmation if state.get("security_decision") else False,
                    "execute_success": False,
                    "execute_error": "meta_not_allowed_in_stage",
                    "exec_result_path": None,
                    "planner_raw_path": str(planner_result.raw_path) if planner_result and planner_result.raw_path else None,
                    "loop_trigger": state.get("loop_trigger"),
                    "stop_reason": "planner_disallowed_action",
                    "stop_details": f"action={action.get('action')}; stage={state.get('goal_stage')}",
                }
                records.append(record)
                if trace:
                    try:
                        trace.write(record)
                    except Exception:
                        pass
                return {**state, "records": records, "stop_reason": "planner_disallowed_action", "stop_details": f"action={action.get('action')}; stage={state.get('goal_stage')}"}
            record = {
                "step": state.get("step", 0),
                "session_id": state["session_id"],
                "step_id": step_id,
                "action": action,
                "planner_retries": planner_result.retries_used if planner_result else 0,
                "security_requires_confirmation": state.get("security_decision").requires_confirmation if state.get("security_decision") else False,
                "execute_success": True,
                "execute_error": None,
                "exec_result_path": None,
                "planner_raw_path": str(planner_result.raw_path) if planner_result and planner_result.raw_path else None,
                "loop_trigger": state.get("loop_trigger"),
                "stop_reason": f"meta_{action.get('action')}",
                "stop_details": None,
            }
            records = state.get("records", [])
            records.append(record)
            if trace:
                try:
                    trace.write(record)
                except Exception:
                    pass
            return {
                **state,
                "records": records,
                "stop_reason": f"meta_{action.get('action')}",
                "stop_details": None,
                "exec_result": None,
            }

        if not execute_enabled:
            text_log.write(f"[{step_id}] execute disabled")
            exec_success = None
            exec_error = "Execution disabled"
        else:
            try:
                try:
                    exec_result, new_obs = await asyncio.wait_for(
                        execute_with_fallbacks(
                            await runtime.ensure_page(),
                            settings,
                            action,
                            observation,
                            max_reobserve_attempts=settings.max_reobserve_attempts,
                            observation_label=f"{state['session_id']}-step{state.get('step', 0)}",
                            trace=trace,
                            session_id=state["session_id"],
                            step=state.get("step", 0),
                        ),
                        timeout=settings.execute_timeout_sec,
                    )
                except Exception as exc:
                    if not runtime.is_target_closed_error(exc):
                        raise
                    text_log.write(f"[{state['session_id']}] TargetClosed detected at step={state.get('step', 0)}; retrying execute")
                    exec_result, new_obs = await asyncio.wait_for(
                        execute_with_fallbacks(
                            await runtime.ensure_page(),
                            settings,
                            action,
                            observation,
                            max_reobserve_attempts=settings.max_reobserve_attempts,
                            observation_label=f"{state['session_id']}-step{state.get('step', 0)}",
                        ),
                        timeout=settings.execute_timeout_sec,
                    )
                exec_result_path = save_execution_result(
                    exec_result,
                    settings.paths.state_dir,
                    label=f"{state['session_id']}-step{state.get('step', 0)}",
                )
                exec_success = exec_result.success
                exec_error = exec_result.error
                observation = new_obs
                state["observation"] = observation
                text_log.write(f"[{step_id}] execute {'success' if exec_success else 'failed'} action={action} err={exec_error}")
            except asyncio.TimeoutError:
                exec_success = False
                exec_error = "Execute timeout"
                text_log.write(f"[{step_id}] execute timeout; stopping")
                record = {
                    "step": state.get("step", 0),
                    "session_id": state["session_id"],
                    "step_id": step_id,
                    "action": action,
                    "planner_retries": planner_result.retries_used if planner_result else 0,
                    "security_requires_confirmation": state.get("security_decision").requires_confirmation if state.get("security_decision") else False,
                    "execute_success": exec_success,
                    "execute_error": exec_error,
                    "exec_result_path": None,
                    "planner_raw_path": str(planner_result.raw_path) if planner_result and planner_result.raw_path else None,
                    "loop_trigger": state.get("loop_trigger"),
                    "stop_reason": "execute_timeout",
                    "stop_details": f"step={state.get('step', 0)}",
                    "loop_trigger_sig": state.get("loop_trigger_sig"),
                    "attempts_per_element": state.get("exec_fail_counts", {}),
                }
                records = state.get("records", [])
                records.append(record)
                if trace:
                    try:
                        trace.write(record)
                    except Exception:
                        pass
                return {**state, "records": records, "stop_reason": "execute_timeout", "stop_details": f"step={state.get('step', 0)}"}
            except Exception as exc:
                exec_success = False
                exec_error = str(exc)
                text_log.write(f"[{step_id}] execute failed: {exc}")

        visited_elements = state.get("visited_elements", {})
        visited_urls = state.get("visited_urls", {})
        avoid = set(state.get("avoid_elements", []))
        if observation:
            url = observation.url
            visited_urls[url] = visited_urls.get(url, 0) + 1
        elem_id = action.get("element_id")
        if elem_id is not None:
            key = str(elem_id)
            visited_elements[key] = visited_elements.get(key, 0) + 1
            if exec_success is False:
                avoid.add(key)
            fail_counts = state.get("exec_fail_counts", {})
            fail_counts[key] = fail_counts.get(key, 0) + 1
            if fail_counts[key] >= settings.max_attempts_per_element:
                avoid.add(key)
            state["exec_fail_counts"] = fail_counts

        url_changed = bool(obs_before and observation and obs_before.url != observation.url)
        dom_changed = bool(_mapping_hash(obs_before) != _mapping_hash(observation)) if obs_before and observation else False
        state["last_state_change"] = {"url_changed": url_changed, "dom_changed": dom_changed}
        state["last_action_no_effect"] = not url_changed and not dom_changed

        record = {
            "step": state.get("step", 0),
            "session_id": state["session_id"],
            "step_id": step_id,
            "action": action,
            "planner_retries": planner_result.retries_used if planner_result else 0,
            "security_requires_confirmation": state.get("security_decision").requires_confirmation if state.get("security_decision") else False,
            "execute_success": exec_success,
            "execute_error": exec_error,
            "exec_result_path": str(exec_result_path) if exec_result_path else None,
            "planner_raw_path": str(planner_result.raw_path) if planner_result and planner_result.raw_path else None,
            "loop_trigger": state.get("loop_trigger"),
            "stop_reason": state.get("stop_reason"),
            "stop_details": state.get("stop_details"),
            "url_changed": url_changed,
            "dom_changed": dom_changed,
            "loop_trigger_sig": state.get("loop_trigger_sig"),
            "attempts_per_element": state.get("exec_fail_counts", {}),
            "max_attempts_per_element": settings.max_attempts_per_element,
        }

        records = state.get("records", [])
        records.append(record)
        if trace:
            try:
                trace.write(record)
            except Exception:
                pass

        action_history = state.get("action_history", [])
        action_history.append(
            {
                "action": action.get("action"),
                "element_id": action.get("element_id"),
                "url": observation.url if observation else None,
                "url_changed": url_changed,
                "dom_changed": dom_changed,
            }
        )

        return {
            **state,
            "planner_result": planner_result,
            "exec_result": exec_result,
            "records": records,
            "visited_elements": visited_elements,
            "visited_urls": visited_urls,
            "avoid_elements": list(avoid),
            "last_error_context": exec_error if exec_success is False else None,
            "action_history": action_history,
            "recent_observations": list((state.get("recent_observations") or [])[-2:]) + ([observation] if observation else []),
        }

    async def progress_node(state: GraphState) -> GraphState:
        observation = state["observation"]
        prev_observation = state.get("prev_observation")
        action = state.get("planner_result").action if state.get("planner_result") else {}
        if observation is None:
            return state

        score, evidence, url_changed, detail_confidence, mapping_goal_hits, listing_score, detail_score = _progress_score(
            state["goal"],
            prev_observation,
            observation,
            action or {},
            [kw.lower() for kw in settings.progress_keywords],
        )
        state_changed = url_changed or (_mapping_hash(prev_observation) != _mapping_hash(observation) if prev_observation else False)
        page_type = _page_type_from_scores(listing_score, detail_score, detail_confidence)
        # Console evidence for transparency
        print(f"[graph] progress score={score} evidence={evidence} url_changed={url_changed} detail_confidence={detail_confidence} listing_score={listing_score} detail_score={detail_score}")
        # If we reached a detail-like page or single-result after goal hit, allow done/ask_user even if detail_confidence is false.
        single_hit = mapping_goal_hits >= 1 and listing_score <= 5
        if state_changed and score >= max(1, settings.auto_done_threshold) and not (page_type == "listing" and not detail_confidence and not single_hit):
            require_url = settings.auto_done_require_url_change
            mode = settings.auto_done_mode
            find_only = _goal_is_find_only(state["goal"])
            list_like = listing_score > detail_score and not detail_confidence
            # Do not auto stop in context/locate stages; goal_satisfied handled in goal_check.
            if state.get("goal_stage") in {"orient", "context"}:
                pass
            elif mode == "auto" and detail_confidence and (not require_url or url_changed):
                state["records"].append(
                    {
                        "step": state.get("step", 0),
                        "session_id": state["session_id"],
                        "step_id": generate_step_id(f"{state['session_id']}-progress"),
                        "action": {"action": "done", "tool": "browser_action", "element_id": None, "value": None},
                        "planner_retries": state.get("planner_result").retries_used if state.get("planner_result") else 0,
                        "security_requires_confirmation": False,
                        "execute_success": True,
                        "execute_error": None,
                        "exec_result_path": None,
                        "planner_raw_path": str(state.get("planner_result").raw_path) if state.get("planner_result") and state.get("planner_result").raw_path else None,
                        "loop_trigger": state.get("loop_trigger"),
                        "stop_reason": "progress_auto_done",
                        "stop_details": str(evidence),
                    }
                )
                if trace:
                    try:
                        trace.write(state["records"][-1])
                    except Exception:
                        pass
                    return {**state, "stop_reason": "progress_auto_done", "stop_details": str(evidence)}
            if find_only or list_like or (require_url and not url_changed) or not detail_confidence:
                if state.get("goal_stage") in {"orient", "context"}:
                    pass
                else:
                    if not INTERACTIVE_PROMPTS:
                        # Non-interactive mode: surface ask_user as terminal without blocking.
                        state["records"].append(
                            {
                                "step": state.get("step", 0),
                                "session_id": state["session_id"],
                                "step_id": generate_step_id(f"{state['session_id']}-progress"),
                                "action": {"action": "ask_user", "tool": "browser_action", "element_id": None, "value": None},
                                "planner_retries": state.get("planner_result").retries_used if state.get("planner_result") else 0,
                                "security_requires_confirmation": False,
                                "execute_success": True,
                                "execute_error": None,
                                "exec_result_path": None,
                                "planner_raw_path": str(state.get("planner_result").raw_path) if state.get("planner_result") and state.get("planner_result").raw_path else None,
                                "loop_trigger": state.get("loop_trigger"),
                                "stop_reason": "progress_ask_user",
                                "stop_details": str(evidence),
                            }
                        )
                        if trace:
                            try:
                                trace.write(state["records"][-1])
                            except Exception:
                                pass
                        return {**state, "stop_reason": "progress_ask_user", "stop_details": str(evidence)}
                    reply = input("[graph] Looks like goal may be done. Stop? (y/N): ").strip().lower()
                    if reply in {"y", "yes"}:
                        state["records"].append(
                            {
                                "step": state.get("step", 0),
                                "session_id": state["session_id"],
                                "step_id": generate_step_id(f"{state['session_id']}-progress"),
                                "action": {"action": "ask_user", "tool": "browser_action", "element_id": None, "value": None},
                                "planner_retries": state.get("planner_result").retries_used if state.get("planner_result") else 0,
                                "security_requires_confirmation": False,
                                "execute_success": True,
                                "execute_error": None,
                                "exec_result_path": None,
                                "planner_raw_path": str(state.get("planner_result").raw_path) if state.get("planner_result") and state.get("planner_result").raw_path else None,
                                "loop_trigger": state.get("loop_trigger"),
                                "stop_reason": "progress_ask_user",
                                "stop_details": str(evidence),
                            }
                        )
                        if trace:
                            try:
                                trace.write(state["records"][-1])
                            except Exception:
                                pass
                        return {**state, "stop_reason": "progress_ask_user", "stop_details": str(evidence)}

        # loop repeat tracking
        sig = (action.get("action"), action.get("element_id"), observation.url)
        last_sig = state.get("loop_trigger_sig")
        repeat_count = state.get("repeat_count", 0)
        if sig == last_sig:
            repeat_count += 1
        else:
            repeat_count = 0
        no_prog = state.get("no_progress_steps", 0)
        if not state_changed:
            no_prog += 1
        else:
            no_prog = 0
        return {
            **state,
            "repeat_count": repeat_count,
            "loop_trigger_sig": sig,
            "last_progress_score": score,
            "last_progress_evidence": evidence,
            "step": state.get("step", 0) + 1,
            "page_type": page_type,
            "no_progress_steps": no_prog,
        }

    async def ask_user_node(state: GraphState) -> GraphState:
        reason = state.get("stop_reason")
        details = state.get("stop_details")
        obs = state.get("observation")
        goal = state.get("goal")
        evidence = state.get("last_progress_evidence")
        url = obs.url if obs else None
        title = obs.title if obs else None
        if not INTERACTIVE_PROMPTS:
            # Non-interactive: do not block, return as-is (stop_reason already set).
            record = {
                "step": state.get("step", 0),
                "session_id": state["session_id"],
                "node": "ask_user",
                "decision": "auto_stop",
                "stop_reason": reason,
                "evidence": evidence,
                "url": url,
                "title": title,
            }
            if trace:
                try:
                    trace.write(record)
                except Exception:
                    pass
            return state
        print("\n[graph] Агент считает, что цель может быть выполнена.")
        print(f"[graph] goal={goal}")
        print(f"[graph] url={url}")
        print(f"[graph] title={title}")
        print(f"[graph] reason={reason} details={details}")
        print(f"[graph] evidence={evidence}")
        reply = input("[graph] Завершить выполнение? (y/N): ").strip().lower()
        if reply in {"y", "yes", "д", "да"}:
            record = {
                "step": state.get("step", 0),
                "session_id": state["session_id"],
                "node": "ask_user",
                "decision": "confirm",
                "stop_reason": "user_confirm_done",
                "evidence": evidence,
                "url": url,
                "title": title,
            }
            if trace:
                try:
                    trace.write(record)
                except Exception:
                    pass
            return {**state, "stop_reason": "user_confirm_done"}
        record = {
            "step": state.get("step", 0),
            "session_id": state["session_id"],
            "node": "ask_user",
            "decision": "continue",
            "stop_reason": None,
            "evidence": evidence,
            "url": url,
            "title": title,
        }
        if trace:
            try:
                trace.write(record)
            except Exception:
                pass
        return {**state, "stop_reason": None, "stop_details": None}

    async def error_retry_node(state: GraphState) -> GraphState:
        retries = state.get("error_retries", 0)
        if retries >= 1:
            return state
        text_log.write(f"[{state['session_id']}] retry after error {state.get('stop_reason')}")
        record = {
            "step": state.get("step", 0),
            "session_id": state["session_id"],
            "node": "error_retry",
            "stop_reason": state.get("stop_reason"),
            "stop_details": state.get("stop_details"),
            "error_retries": retries + 1,
        }
        if trace:
            try:
                trace.write(record)
            except Exception:
                pass
        return {
            **state,
            "stop_reason": None,
            "stop_details": None,
            "error_retries": retries + 1,
            "last_error_context": state.get("stop_reason"),
        }

    workflow.add_node("observe", observe_node)
    workflow.add_node("loop_mitigation", loop_mitigation_node)
    workflow.add_node("goal_check", goal_check_node)
    workflow.add_node("planner", planner_node)
    workflow.add_node("safety", safety_node)
    workflow.add_node("confirm", confirm_node)
    workflow.add_node("execute", execute_node)
    workflow.add_node("progress", progress_node)
    workflow.add_node("ask_user", ask_user_node)
    workflow.add_node("error_retry", error_retry_node)

    workflow.add_edge(START, "observe")
    workflow.add_conditional_edges(
        "observe",
        lambda state: END if state.get("stop_reason") else ("loop_mitigation" if state.get("loop_trigger") else "goal_check"),
        {"loop_mitigation": "loop_mitigation", "goal_check": "goal_check", END: END},
    )
    workflow.add_conditional_edges(
        "goal_check",
        lambda state: END if state.get("stop_reason") else "planner",
        {"planner": "planner", END: END},
    )
    workflow.add_edge("loop_mitigation", "planner")
    workflow.add_conditional_edges(
        "planner",
        lambda state: "error_retry"
        if state.get("stop_reason") in {"planner_error", "planner_timeout", "planner_disallowed_action"}
        else ("safety" if not state.get("stop_reason") else END),
        {"safety": "safety", "error_retry": "error_retry", END: END},
    )
    workflow.add_conditional_edges(
        "safety",
        lambda state: "confirm" if state["security_decision"].requires_confirmation else "execute",
        {"confirm": "confirm", "execute": "execute"},
    )
    workflow.add_conditional_edges(
        "confirm",
        lambda state: "execute" if not state.get("stop_reason") else END,
        {"execute": "execute", END: END},
    )
    workflow.add_conditional_edges(
        "execute",
        lambda state: "error_retry" if state.get("stop_reason") in {"execute_timeout", "execute_error"} else ("progress" if not state.get("stop_reason") else END),
        {"progress": "progress", "error_retry": "error_retry", END: END},
    )
    workflow.add_conditional_edges(
        "progress",
        lambda state: "ask_user" if state.get("stop_reason") == "progress_ask_user" else (END if state.get("stop_reason") else "observe"),
        {"observe": "observe", "ask_user": "ask_user", END: END},
    )
    workflow.add_conditional_edges(
        "error_retry",
        lambda state: "observe" if not state.get("stop_reason") else END,
        {"observe": "observe", END: END},
    )
    workflow.add_conditional_edges(
        "ask_user",
        lambda state: END if state.get("stop_reason") else "observe",
        {"observe": "observe", END: END},
    )

    graph = workflow.compile()

    async def run(goal: str) -> dict[str, Any]:
        session_id = generate_step_id("session")
        initial_state: GraphState = {
            "goal": goal,
            "goal_kind": _classify_goal_kind(goal),
            "goal_stage": "orient",
            "artifact_detected": False,
            "artifact_type": None,
            "session_id": session_id,
            "step": 1,
            "repeat_count": 0,
            "stagnation_count": 0,
            "auto_scrolls_used": 0,
            "avoid_elements": [],
            "visited_urls": {},
            "visited_elements": {},
            "action_history": [],
            "records": [],
            "exec_fail_counts": {},
            "recent_observations": [],
            "conservative_probe_done": False,
            "error_retries": 0,
            "loop_mitigated": False,
            "progress_steps": 0,
            "no_progress_steps": 0,
            "planner_calls": 0,
        }
        try:
            result = await graph.ainvoke(initial_state, config=graph_config)
        except Exception as exc:
            # Graceful handling of recursion limit (or similar graph errors)
            from langgraph.errors import GraphRecursionError  # type: ignore

            if isinstance(exc, GraphRecursionError):
                if text_log:
                    try:
                        text_log.write(f"[{session_id}] recursion limit reached; reason={exc}")
                    except Exception:
                        pass
                result = {
                    "goal": goal,
                    "session_id": session_id,
                    "stop_reason": "budget_exhausted",
                    "stop_details": f"recursion_limit; {exc}",
                    "planner_calls": 0,
                    "observation": initial_state.get("observation"),
                }
            else:
                raise
        try:
            # Normalize terminal reason/type and enforce invariant.
            stop_reason = result.get("stop_reason")
            if not stop_reason:
                stop_reason = "goal_failed"
                result["stop_reason"] = stop_reason
                result["stop_details"] = "no_stop_condition_reached"
            terminal_reason = result.get("terminal_reason") or STOP_TO_TERMINAL.get(stop_reason) or "goal_failed"
            result["terminal_reason"] = terminal_reason
            result["terminal_type"] = TERMINAL_TYPES.get(terminal_reason, "failure")
            text_log.write(
                f"[{session_id}] finished reason={result.get('stop_reason')} terminal={result.get('terminal_type')} "
                f"stage={result.get('goal_stage')} details={result.get('stop_details')} "
                f"url={(result.get('observation').url if result.get('observation') else None)} "
                f"progress={result.get('last_progress_score')} evidence={result.get('last_progress_evidence')}"
            )
            if trace:
                trace.write(
                    {
                        "summary": True,
                        "session_id": session_id,
                        "stop_reason": result.get("stop_reason"),
                        "stop_details": result.get("stop_details"),
                        "terminal_reason": result.get("terminal_reason"),
                        "terminal_type": result.get("terminal_type"),
                        "goal_stage": result.get("goal_stage"),
                        "url": result.get("observation").url if result.get("observation") else None,
                        "progress": result.get("last_progress_score"),
                        "evidence": result.get("last_progress_evidence"),
                    }
                )
        except Exception:
            pass
        return result

    return run
