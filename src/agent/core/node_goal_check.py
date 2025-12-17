from __future__ import annotations

from typing import Any, Optional

from agent.config.config import Settings
from agent.core.graph_state import (
    GraphState,
    INTERACTIVE_PROMPTS,
    TERMINAL_TYPES,
    classify_goal_kind,
    goal_tokens,
    mapping_hash,
    page_type_from_scores,
    progress_score,
    promote_stage,
)


def _goal_checker(
    state: GraphState,
    observation,
    *,
    goal_tokens_list,
    page_type: str,
    listing_score: int,
    detail_score: int,
    detail_confidence: bool,
    no_progress_steps: int,
    max_no_progress_steps: int,
    planner_calls: int,
    max_planner_calls: int,
):
    stage = state.get("goal_stage", "orient")
    goal_kind = state.get("goal_kind", "object")
    evidence = []
    artifact_detected = False
    artifact_type = "none"

    url_title = (observation.url + " " + observation.title).lower()
    goal_hit_url_title = any(tok in url_title for tok in goal_tokens_list if tok)
    mapping_text = " ".join((m.text or "") for m in observation.mapping).lower()
    mapping_goal_hits = sum(1 for tok in goal_tokens_list if tok in mapping_text)

    if goal_hit_url_title or mapping_goal_hits > 0:
        stage = promote_stage(stage, "context")
    if page_type == "listing" and mapping_goal_hits > 0:
        stage = promote_stage(stage, "locate")
    if page_type == "detail" and goal_hit_url_title:
        stage = promote_stage(stage, "verify")

    if goal_kind == "object":
        detail_url_hit = "/vault/" in observation.url or any(ch.isdigit() for ch in observation.url.split("/")[-1])
        if detail_url_hit and goal_hit_url_title:
            artifact_detected = True
            artifact_type = "detail"
            evidence.append("object_detail_url")
            stage = promote_stage(stage, "verify")
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
        fulfilled = False

    failed = False
    fail_reason = ""
    if not artifact_detected and no_progress_steps >= max_no_progress_steps and stage in {"orient", "context"}:
        failed = True
        fail_reason = f"insufficient_knowledge:no_progress_steps={no_progress_steps}"
    if not artifact_detected and planner_calls >= max_planner_calls:
        failed = True
        fail_reason = f"llm_budget_exhausted:planner_calls={planner_calls}"

    return stage, fulfilled, artifact_type, evidence, artifact_detected, failed, fail_reason


def make_goal_check_node(
    *,
    settings: Settings,
) -> Any:
    async def goal_check_node(state: GraphState) -> GraphState:
        observation = state["observation"]
        if observation is None:
            return state
        prev_observation = state.get("prev_observation")
        last_action = state.get("planner_result").action if state.get("planner_result") else (state.get("action_history", [])[-1] if state.get("action_history") else {})
        if state.get("step", 0) >= settings.max_steps:
            return {
                **state,
                "stop_reason": "budget_exhausted",
                "stop_details": f"max_steps={settings.max_steps}",
                "terminal_reason": "budget_exhausted",
                "terminal_type": TERMINAL_TYPES.get("budget_exhausted"),
            }
        score_ctx = progress_score(
            state["goal"],
            prev_observation,
            observation,
            last_action or {},
            [kw.lower() for kw in settings.progress_keywords],
        )
        (_, _, _, detail_confidence, _, listing_score, detail_score) = score_ctx
        page_type = page_type_from_scores(listing_score, detail_score, detail_confidence)
        goal_stage, fulfilled, artifact_type, goal_evidence, artifact_detected, failed, fail_reason = _goal_checker(
            state,
            observation,
            goal_tokens_list=goal_tokens(state["goal"]),
            page_type=page_type,
            listing_score=listing_score,
            detail_score=detail_score,
            detail_confidence=detail_confidence,
            no_progress_steps=state.get("no_progress_steps", 0),
            max_no_progress_steps=settings.max_no_progress_steps,
            planner_calls=state.get("planner_calls", 0),
            max_planner_calls=settings.max_planner_calls,
        )
        stage_not_advanced = (
            not artifact_detected
            and goal_stage in {"orient", "context"}
            and state.get("planner_calls", 0) >= max(2, settings.max_planner_calls // 2)
            and state.get("step", 0) >= max(3, settings.max_steps // 2)
        )
        if stage_not_advanced and not failed:
            failed = True
            fail_reason = f"insufficient_knowledge:stage_not_advanced stage={goal_stage} planner_calls={state.get('planner_calls', 0)} step={state.get('step', 0)}"
        repeat = state.get("repeat_count", 0)
        stagnation = state.get("stagnation_count", 0)
        auto_scrolls = state.get("auto_scrolls_used", 0)
        url_same = bool(prev_observation and prev_observation.url == observation.url)
        dom_same = bool(mapping_hash(prev_observation) == mapping_hash(observation)) if prev_observation else False
        candidates_same = bool(state.get("prev_candidate_hash") is not None and state.get("prev_candidate_hash") == state.get("candidate_hash"))
        no_progress_budget = state.get("no_progress_steps", 0) >= settings.max_no_progress_steps
        counters_exhausted = repeat >= settings.loop_repeat_threshold and stagnation >= settings.stagnation_threshold and auto_scrolls >= settings.max_auto_scrolls
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
                "stop_details": f"repeat={repeat}; stagnation={stagnation}; auto_scrolls={auto_scrolls}; world_frozen={world_frozen}",
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

    return goal_check_node
