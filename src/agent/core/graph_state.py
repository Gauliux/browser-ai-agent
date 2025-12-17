from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, TypedDict

from agent.core.observe import Observation

# Terminal constants retained from monolithic loop.
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
    planner_result: Any
    security_decision: Any
    exec_result: Any
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
    tabs: List[Dict[str, Any]]
    active_tab_id: Optional[str]
    tab_events: List[Dict[str, Any]]
    context_events: List[Dict[str, Any]]
    intent_text: Optional[str]
    intent_history: List[Dict[str, Any]]
    ux_messages: List[str]


def mapping_hash(obs: Optional[Observation]) -> Optional[int]:
    if not obs:
        return None
    return hash(tuple((el.tag, el.text, el.role) for el in obs.mapping))


def candidate_hash(candidates: Optional[List[Dict[str, Any]]]) -> Optional[int]:
    if not candidates:
        return None
    try:
        return hash(tuple((c.get("id"), c.get("text"), c.get("role")) for c in candidates))
    except Exception:
        return None


def goal_tokens(goal: str) -> list[str]:
    return [tok.lower() for tok in goal.replace(",", " ").split() if len(tok) > 3]


def goal_tokens_from_title(title: str) -> list[str]:
    return [t for t in title.lower().replace(",", " ").split() if len(t) > 3]


def goal_is_find_only(goal: str) -> bool:
    goal_low = goal.lower()
    download_verbs = ["download", "скачай", "скачать", "add to cart", "добавь", "купить", "закажи", "оформи"]
    return not any(v in goal_low for v in download_verbs)


def classify_task_mode(goal: str) -> str:
    goal_low = goal.lower()
    if any(k in goal_low for k in ["найди", "ищи", "find", "search", "достань", "добыть"]):
        return "find"
    if any(k in goal_low for k in ["ответ", "поясни", "explain", "answer"]):
        return "answer"
    if any(k in goal_low for k in ["скачай", "download"]):
        return "download"
    return "browse"


def page_type_from_scores(listing_score: int, detail_score: int, detail_confidence: bool) -> str:
    if detail_confidence:
        return "detail"
    if listing_score > detail_score + 2:
        return "listing"
    return "unknown"


def extract_candidates(mapping: List[Any], goal_tokens_list: List[str], limit: int = 10) -> List[Dict[str, Any]]:
    scored: List[tuple[int, Any]] = []
    for el in mapping:
        text = (getattr(el, "text", "") or "").lower()
        role = (getattr(el, "role", "") or "").lower()
        tag = (getattr(el, "tag", "") or "").lower()
        score = 0
        for tok in goal_tokens_list:
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
                "zone": getattr(el, "zone", None),
                "is_nav": getattr(el, "is_nav", False),
                "is_disabled": getattr(el, "is_disabled", False),
            }
        )
    return result


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


def score_action_candidate(candidate: Dict[str, Any], observation: Observation, state: GraphState) -> int:
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
    if candidate.get("is_nav"):
        score -= 5
    zone = candidate.get("zone")
    if zone is not None and zone > 2:
        score -= 2
    if any(w in text for w in ["cart", "basket", "корзина"]):
        score -= 3
    return score


def pick_committed_action(
    candidates: List[Dict[str, Any]],
    observation: Observation,
    state: GraphState,
    threshold: int = 8,
) -> Optional[Dict[str, Any]]:
    if not candidates:
        return None
    scored = [(score_action_candidate(c, observation, state), c) for c in candidates]
    scored.sort(key=lambda x: x[0], reverse=True)
    best_score, best = scored[0]
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


def progress_score(
    goal: str,
    prev_observation: Optional[Observation],
    current_observation: Observation,
    last_action: Dict[str, Any],
    keywords: List[str],
) -> tuple[int, list[str], bool, bool, int, int, int]:
    evidence: list[str] = []
    score = 0

    goal_tokens_list = goal_tokens(goal)
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

    goal_hits = [tok for tok in goal_tokens_list if tok in mapping_text or tok in url_lower]
    if goal_hits:
        score += 1
        evidence.append(f"goal_hits:{goal_hits}")

    mapping_goal_hits_count = sum(1 for tok in goal_tokens_list if tok in mapping_text)

    detail_confidence = False
    title_lower = current_observation.title.lower()
    title_hits = [tok for tok in goal_tokens_list if tok in title_lower]
    if title_hits and len(title_hits) >= max(1, len(goal_tokens_list) // 2):
        detail_confidence = True
        evidence.append(f"title_hits:{title_hits}")
        score += 1

    path_hits = [tok for tok in goal_tokens_list if tok in url_lower]
    if path_hits and len(path_hits) >= max(1, len(goal_tokens_list) // 2):
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

    links = sum(1 for m in current_observation.mapping if (m.role or "").lower() in {"link", "button"} or m.tag in {"a", "button"})
    inputs = sum(1 for m in current_observation.mapping if m.tag in {"input", "textarea", "select"})
    listing_score = links + inputs
    detail_score = len([m for m in current_observation.mapping if len((m.text or "")) > 40])

    return score, evidence, url_changed, detail_confidence, mapping_goal_hits_count, listing_score, detail_score


def classify_goal_kind(goal: str) -> str:
    gl = goal.lower()
    if any(k in gl for k in ["список", "list", "перевод", "translations", "results"]):
        return "list"
    if any(k in gl for k in ["добавь", "добавить", "купи", "в корзину", "buy", "add to cart", "order", "закажи"]):
        return "action"
    return "object"


def stage_rank(stage: str) -> int:
    order = ["orient", "context", "locate", "verify", "done"]
    return order.index(stage) if stage in order else 0


def promote_stage(current: str, proposed: str) -> str:
    return proposed if stage_rank(proposed) > stage_rank(current) else current
