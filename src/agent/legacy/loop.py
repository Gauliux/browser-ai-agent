from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from agent.config.config import Settings
from agent.core.observe import capture_observation, Observation
from agent.core.execute import execute_with_fallbacks, save_execution_result
from agent.infra.runtime import BrowserRuntime
from agent.core.planner import Planner
from agent.core.security import SecurityDecision, analyze_action, prompt_confirmation
from agent.legacy.state import AgentState
from agent.infra.tracing import TextLogger, TraceLogger, generate_step_id


@dataclass
class StepRecord:
    step: int
    session_id: str
    step_id: str
    action: Dict[str, Any]
    planner_retries: int
    security: SecurityDecision
    execute_success: Optional[bool]
    execute_error: Optional[str]
    observation: Observation
    exec_result_path: Optional[Path]
    planner_raw_path: Optional[Path]
    notes: str = ""
    loop_trigger: Optional[str] = None
    stop_reason: Optional[str] = None
    stop_details: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "step_id": self.step_id,
            "step": self.step,
            "action": self.action,
            "planner_retries": self.planner_retries,
            "security_requires_confirmation": self.security.requires_confirmation,
            "security_reason": self.security.reason,
            "execute_success": self.execute_success,
            "execute_error": self.execute_error,
            "exec_result_path": str(self.exec_result_path) if self.exec_result_path else None,
            "planner_raw_path": str(self.planner_raw_path) if self.planner_raw_path else None,
            "observation": self.observation.to_dict(),
            "notes": self.notes,
            "loop_trigger": self.loop_trigger,
            "stop_reason": self.stop_reason,
            "stop_details": self.stop_details,
        }


class AgentLoop:
    def __init__(
        self,
        settings: Settings,
        planner: Planner,
        agent_state: AgentState,
        execute_enabled: bool,
        runtime: BrowserRuntime,
    ) -> None:
        self.settings = settings
        self.planner = planner
        self.agent_state = agent_state
        self.execute_enabled = execute_enabled
        self.runtime = runtime
        self.trace = TraceLogger(settings.paths.logs_dir / "trace.jsonl")
        self.text_log = TextLogger(settings.paths.logs_dir / "agent.log")
        self._reset_tracking()

    def _reset_tracking(self) -> None:
        self.last_action_sig: Optional[tuple] = None
        self.repeat_count: int = 0
        self.mapping_hash: Optional[int] = None
        self.stagnation_count: int = 0
        self.auto_scrolls_used: int = 0
        self.visited_elements: dict[str, int] = {}
        self.visited_urls: dict[str, int] = {}
        self.avoid_elements: set[str] = set()
        self.exec_fail_counts: dict[str, int] = {}
        self.last_error_context: Optional[str] = None
        self.stuck_count: int = 0
        self.last_progress_score: Optional[int] = None
        self.last_progress_evidence: Optional[list[str]] = None
        self.action_history: list[dict[str, Any]] = []

    async def _capture_with_retry(
        self,
        page,
        *,
        viewports: int = 1,
        label: Optional[str] = None,
        capture_screenshot: Optional[bool] = None,
        max_elements: Optional[int] = None,
    ) -> Observation:
        setattr(page, "_hide_overlay", self.settings.hide_overlay)
        try:
            return await capture_observation(
                page,
                self.settings,
                viewports=viewports,
                label=label,
                capture_screenshot=capture_screenshot,
                max_elements=max_elements,
            )
        except Exception as exc:
            if not self.runtime.is_target_closed_error(exc):
                raise
            self.text_log.write(f"[{label or 'observe'}] page closed detected; retrying capture on a live page")
            page = await self._ensure_page()
            setattr(page, "_hide_overlay", self.settings.hide_overlay)
            return await capture_observation(
                page,
                self.settings,
                viewports=viewports,
                label=label,
                capture_screenshot=capture_screenshot,
                max_elements=max_elements,
            )

    def _decide_include_screenshot(self, observation: Observation) -> bool:
        mode = self.settings.planner_screenshot_mode
        if mode == "always":
            return True
        if mode == "never":
            return False
        return len(observation.mapping) <= max(10, int(self.settings.mapping_limit * 0.5))

    def _log_zone_counts(self, label: str, observation: Observation) -> None:
        zones: dict[int, int] = {}
        for m in observation.mapping:
            if m.zone is None:
                continue
            zones[m.zone] = zones.get(m.zone, 0) + 1
        if zones:
            counts = ", ".join(f"{z}:{cnt}" for z, cnt in sorted(zones.items()))
            self.text_log.write(f"{label} zones {{{counts}}}")

    async def _paged_scan(self, page, *, label_prefix: Optional[str] = None) -> Observation:
        """Perform small-step paged scanning (downward) and merge observations."""
        combined_mapping: list = []
        screenshots: list[Path] = []
        last_obs: Optional[Observation] = None
        steps = max(1, self.settings.paged_scan_steps)
        viewports = max(1, self.settings.paged_scan_viewports)

        for i in range(steps):
            obs = await self._capture_with_retry(
                page,
                viewports=viewports,
                label=f"{label_prefix}-scan{i}" if label_prefix else None,
            )
            combined_mapping.extend(obs.mapping)
            screenshots.append(obs.screenshot_path)
            last_obs = obs
            # small scroll except after last
            if i < steps - 1:
                try:
                    await page.mouse.wheel(0, 350)
                except Exception:
                    pass

        if not last_obs:
            return await self._capture_with_retry(page, viewports=viewports)

        # Deduplicate by id/text/role/bbox to avoid huge duplicates
        seen = set()
        deduped = []
        for m in combined_mapping:
            key = (m.tag, m.text, m.role, int(m.bbox.x), int(m.bbox.y), int(m.bbox.width), int(m.bbox.height))
            if key in seen:
                continue
            seen.add(key)
            deduped.append(m)

        # Replace mapping with merged, keep last screenshot/title/url
        merged = Observation(
            url=last_obs.url,
            title=last_obs.title,
            mapping=sorted(deduped, key=lambda m: (m.bbox.y, m.bbox.x)),
            screenshot_path=last_obs.screenshot_path,
            recorded_at=last_obs.recorded_at,
        )
        self._log_zone_counts("[paged_scan] merged", merged)
        return merged

    def _progress_context(self, goal: str, observation: Observation) -> str:
        goal_lower = goal.lower()
        mapping_texts = " ".join((el.text or "") + " " + (el.role or "") for el in observation.mapping).lower()
        url_lower = observation.url.lower()
        found = []
        for kw in self.settings.progress_keywords:
            if kw.lower() in mapping_texts or kw.lower() in url_lower:
                found.append(kw)
        goal_tokens = [tok for tok in goal_lower.split() if len(tok) > 3]
        goal_hits = [tok for tok in goal_tokens if tok in mapping_texts]
        return (
            f"keywords_found={found}, goal_hits={goal_hits}, "
            f"url={observation.url}, repeats={self.repeat_count}, stagnation={self.stagnation_count}, "
            f"visited_urls={len(self.visited_urls)}, visited_elements={len(self.visited_elements)}"
        )

    def _goal_tokens(self, goal: str) -> list[str]:
        return [tok.lower() for tok in goal.replace(",", " ").split() if len(tok) > 3]

    def _mapping_hash(self, observation: Optional[Observation]) -> Optional[int]:
        if not observation:
            return None
        return hash(tuple((el.tag, el.text, el.role) for el in observation.mapping))

    def _actions_context(self) -> str:
        if not self.action_history:
            return "none"
        parts = []
        for item in self.action_history[-5:]:
            parts.append(
                f"{item.get('action')} el={item.get('element_id')} url={item.get('url')} "
                f"url_changed={item.get('url_changed')} dom_changed={item.get('dom_changed')}"
            )
        return "; ".join(parts)

    def _progress_score(
        self,
        goal: str,
        prev_observation: Optional[Observation],
        current_observation: Observation,
        last_action: Dict[str, Any],
    ) -> Tuple[int, list[str], bool, bool, int]:
        evidence: list[str] = []
        score = 0
        url_changed = False

        goal_tokens = self._goal_tokens(goal)
        keywords = [kw.lower() for kw in self.settings.progress_keywords]

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

        listing_like = mapping_goal_hits_count >= 3

        return score, evidence, url_changed, detail_confidence, mapping_goal_hits_count

    def _goal_is_find_only(self, goal: str) -> bool:
        goal_low = goal.lower()
        download_verbs = ["download", "скачай", "скачать", "add to cart", "добавь", "купить", "закажи", "оформи"]
        return not any(v in goal_low for v in download_verbs)

    def _decide_progress_stop(
        self,
        goal: str,
        prev_observation: Optional[Observation],
        current_observation: Observation,
        last_action: Dict[str, Any],
    ) -> Tuple[Optional[Dict[str, Any]], int, list[str]]:
        (
            score,
            evidence,
            url_changed,
            detail_confidence,
            mapping_goal_hits_count,
        ) = self._progress_score(goal, prev_observation, current_observation, last_action)
        self.last_progress_score = score
        self.last_progress_evidence = evidence

        # Require some state change (URL or DOM hash) to consider progress
        prev_hash = self._mapping_hash(prev_observation)
        curr_hash = self._mapping_hash(current_observation)
        state_changed = url_changed or (prev_hash is not None and curr_hash is not None and prev_hash != curr_hash)
        if not state_changed:
            return None, score, evidence

        threshold = max(1, self.settings.auto_done_threshold)
        if score < threshold:
            return None, score, evidence

        require_url = self.settings.auto_done_require_url_change
        mode = self.settings.auto_done_mode  # "auto" or "ask"
        find_only = self._goal_is_find_only(goal)

        # Heuristic: if we see many hits (list page) but no detail_confidence, prefer ask_user
        list_like = mapping_goal_hits_count >= 3 and not detail_confidence

        if mode == "auto" and detail_confidence and (not require_url or url_changed):
            action = {
                "tool": "browser_action",
                "action": "done",
                "element_id": None,
                "value": None,
                "requires_confirmation": False,
            }
            return action, score, evidence

        # If goal is find-only and we have high score (even on auto mode), ask user before further actions
        if find_only or list_like or not detail_confidence or (require_url and not url_changed):
            action = {
                "tool": "browser_action",
                "action": "ask_user",
                "element_id": None,
                "value": None,
                "requires_confirmation": False,
            }
            return action, score, evidence

        # Fallback: auto mode without detail confidence defaults to ask_user
        action = {
            "tool": "browser_action",
            "action": "ask_user",
            "element_id": None,
            "value": None,
            "requires_confirmation": False,
        }
        return action, score, evidence

    async def _ensure_page(self):
        # Refresh page reference if closed or missing
        try:
            page = self.runtime.page
            if page.is_closed():
                page = await self.runtime.ensure_page()
        except Exception:
            page = await self.runtime.ensure_page()
        return page

    async def run(self, goal: str) -> None:
        session_id = generate_step_id("session")
        self._reset_tracking()
        page = await self._ensure_page()
        setattr(page, "_hide_overlay", self.settings.hide_overlay)
        observation = await self._capture_with_retry(
            page,
            capture_screenshot=False,
            label=f"{session_id}-step0",
        )
        self.agent_state.add_observation(observation)
        print(f"[loop] Step 0 observation captured ({len(observation.mapping)} elements). URL: {observation.url}")
        if observation.screenshot_path:
            print(f"[loop] Screenshot: {observation.screenshot_path}")
        self.text_log.write(f"[session {session_id}] step 0 observation url={observation.url} elements={len(observation.mapping)}")
        self._log_zone_counts(f"[session {session_id}] step0", observation)
        stop_reason = "max_steps_reached"
        stop_details: Optional[str] = None

        if not self.execute_enabled:
            msg = "[loop] Execution is disabled (plan-only mode); skipping actions for this goal."
            print(msg)
            self.text_log.write(f"[session {session_id}] execution disabled for goal='{goal}'")
            stop_reason = "execution_disabled"
            summary = self._write_summary(session_id, [], observation, stop_reason, "execute flag is off")
            print(f"[loop] Summary: reason={summary['stop_reason']}, last_url={summary['last_url']}")
            return

        step_records = []

        for step in range(1, self.settings.max_steps + 1):
            step_id = generate_step_id(f"{session_id}-step{step}")
            prev_observation_for_progress = observation
            if page.is_closed():
                page = await self._ensure_page()
            setattr(page, "_mapping_boost", 0)

            # Stuck detection: if we've exhausted scrolls and repeats persist
            stuck = (
                self.auto_scrolls_used >= self.settings.max_auto_scrolls
                and self.repeat_count >= self.settings.loop_repeat_threshold
                and self.stagnation_count >= self.settings.stagnation_threshold
            )

            # Detect stagnation by mapping hash
            new_hash = hash(tuple((el.tag, el.text, el.role) for el in observation.mapping))
            if self.mapping_hash is not None and new_hash == self.mapping_hash:
                self.stagnation_count += 1
            else:
                self.stagnation_count = 0
                self.mapping_hash = new_hash

            # If stagnation or repeats exceed thresholds, try auto-scroll and reobserve
            if (
                (self.repeat_count >= self.settings.loop_repeat_threshold)
                or (self.stagnation_count >= self.settings.stagnation_threshold)
            ) and self.auto_scrolls_used < self.settings.max_auto_scrolls:
                self.text_log.write(
                    f"[{step_id}] loop detected (repeat={self.repeat_count}, stagnation={self.stagnation_count}); paged scan to explore new area"
                )
                setattr(page, "_hide_overlay", self.settings.hide_overlay)
                observation = await self._paged_scan(page, label_prefix=step_id)
                self.auto_scrolls_used += 1
                self.agent_state.add_observation(observation)
                self.repeat_count = 0
                self.stagnation_count = 0
                self.mapping_hash = hash(tuple((el.tag, el.text, el.role) for el in observation.mapping))
                print(f"[loop] Paged scan executed; merged observation with {len(observation.mapping)} elements.")
                print(f"[loop] Screenshot: {observation.screenshot_path}")
                self._log_zone_counts(f"[{step_id}] loop-resample", observation)
                continue

            if stuck:
                recent_actions = "; ".join(
                    f"{a.get('action')} el={a.get('element_id')} url_changed={a.get('url_changed')} dom_changed={a.get('dom_changed')}"
                    for a in self.action_history[-3:]
                ) or "none"
                evidence = f"errors={self.last_error_context or 'none'}, progress={self.last_progress_score}/{self.last_progress_evidence}, recent_actions={recent_actions}"
                msg = f"[{step_id}] Stuck detected after max auto-scrolls and repeats; asking user. Evidence: {evidence}"
                print(msg)
                self.text_log.write(msg)
                user_answer = input("[loop] Agent seems stuck. Provide guidance or press Enter to stop: ").strip()
                if user_answer:
                    # Treat user guidance as a new goal suffix to the existing goal
                    goal = f"{goal}. User guidance: {user_answer}"
                    self.text_log.write(f"[{step_id}] Received user guidance, updating goal: {goal}")
                    self.repeat_count = 0
                    self.stagnation_count = 0
                    self.auto_scrolls_used = 0
                    continue
                record = StepRecord(
                    step=step,
                    session_id=session_id,
                    step_id=step_id,
                    action={"action": "ask_user", "tool": "browser_action", "element_id": None, "value": None, "requires_confirmation": False},
                    planner_retries=0,
                    security=SecurityDecision(False, None),
                    execute_success=None,
                    execute_error="Stuck",
                    observation=observation,
                    exec_result_path=None,
                    planner_raw_path=None,
                    notes="stuck",
                    loop_trigger="stuck",
                    stop_reason="stuck",
                    stop_details=evidence,
                )
                self.trace.write(record)
                step_records.append(record)
                stop_reason = "stuck"
                stop_details = evidence
                break

            loop_detected = self.repeat_count >= self.settings.loop_repeat_threshold or self.stagnation_count >= self.settings.stagnation_threshold
            loop_exhausted = loop_detected and self.auto_scrolls_used >= self.settings.max_auto_scrolls
            try:
                # Hint capture/JS about loop for adaptive mapping size.
                setattr(page, "_mapping_boost", self.settings.loop_retry_mapping_boost if loop_detected else 0)
                include_screenshot = True if loop_detected else self._decide_include_screenshot(observation)
                if include_screenshot and not observation.screenshot_path:
                    # Capture screenshot on demand for planner
                    setattr(page, "_hide_overlay", self.settings.hide_overlay)
                    observation = await self._capture_with_retry(
                        page,
                        max_elements=len(observation.mapping),
                        viewports=self.settings.paged_scan_viewports,
                        capture_screenshot=True,
                        label=f"{step_id}-shot",
                    )
                    self.agent_state.add_observation(observation)
                mapping_limit = (
                    self.settings.mapping_limit + self.settings.loop_retry_mapping_boost
                    if loop_detected
                    else self.settings.mapping_limit
                )
                progress_context = self._progress_context(goal, observation)
                actions_context = self._actions_context()
                prev_hash = self._mapping_hash(prev_observation_for_progress)
                curr_hash = self._mapping_hash(observation)
                dom_changed_flag = prev_hash is not None and curr_hash is not None and prev_hash != curr_hash
                listing_detected = False
                # crude listing detection: many goal hits with no url change
                try:
                    _, _, url_changed_tmp, detail_conf, map_goal_hits = self._progress_score(
                        goal, prev_observation_for_progress, observation, {}
                    )
                    if map_goal_hits >= 3 and not url_changed_tmp and not detail_conf:
                        listing_detected = True
                except Exception:
                    pass
                state_change_hint = f"url_changed={dom_changed_flag or (prev_observation_for_progress and prev_observation_for_progress.url != observation.url)}, dom_changed={dom_changed_flag}"
                planner_result = await asyncio.wait_for(
                    self.planner.plan(
                        goal=goal,
                        observation=observation,
                        recent_observations=self.agent_state.recent_observations(limit=3),
                        include_screenshot=include_screenshot,
                        mapping_limit=mapping_limit,
                        max_retries=2,
                        raw_log_dir=self.settings.paths.state_dir if self.settings.enable_raw_logs else None,
                        step_id=step_id,
                        loop_flag=loop_detected,
                        loop_exhausted=loop_exhausted,
                        avoid_elements=sorted(set(self.visited_elements.keys()) | self.avoid_elements),
                        error_context=self.last_error_context,
                        progress_context=progress_context,
                        actions_context=actions_context,
                        listing_detected=listing_detected,
                        state_change_hint=state_change_hint,
                    ),
                    timeout=self.settings.planner_timeout_sec,
                )
            except asyncio.TimeoutError:
                print(f"[loop] Planner timeout at step {step}.")
                self.last_error_context = "planner timeout"
                stop_reason = "planner_timeout"
                stop_details = f"step={step_id}"
                record = StepRecord(
                    step=step,
                    session_id=session_id,
                    step_id=step_id,
                    action={"action": "planner_timeout"},
                    planner_retries=0,
                    security=SecurityDecision(False, None),
                    execute_success=None,
                    execute_error="planner timeout",
                    observation=observation,
                    exec_result_path=None,
                    planner_raw_path=None,
                    notes="planner_timeout",
                    stop_reason=stop_reason,
                    stop_details=stop_details,
                )
                self.trace.write(record)
                step_records.append(record)
                self.text_log.write(f"[{step_id}] planner timeout; stopping")
                break
            except Exception as exc:
                print(f"[loop] Planner failed at step {step}: {exc}")
                self.last_error_context = str(exc)
                stop_reason = "planner_error"
                stop_details = str(exc)
                record = StepRecord(
                    step=step,
                    session_id=session_id,
                    step_id=step_id,
                    action={"action": "planner_error"},
                    planner_retries=0,
                    security=SecurityDecision(False, None),
                    execute_success=None,
                    execute_error=str(exc),
                    observation=observation,
                    exec_result_path=None,
                    planner_raw_path=None,
                    notes="planner_error",
                    stop_reason=stop_reason,
                    stop_details=stop_details,
                )
                self.trace.write(record)
                step_records.append(record)
                self.text_log.write(f"[{step_id}] planner error; stopping: {exc}")
                break

            action = planner_result.action
            print(f"[loop] Step {step} action: {action}")
            print(f"[loop] Current URL: {observation.url}")
            if planner_result.raw_path:
                self.text_log.write(f"[{step_id}] planner raw saved to {planner_result.raw_path}")

            loop_trigger = "loop" if loop_detected else None

            # Exit early on meta actions
            if action.get("action") in {"done", "ask_user"}:
                record = StepRecord(
                    step=step,
                    session_id=session_id,
                    step_id=step_id,
                    action=action,
                    planner_retries=planner_result.retries_used,
                    security=SecurityDecision(False, None),
                    execute_success=True,
                    execute_error=None,
                    observation=observation,
                    exec_result_path=None,
                    planner_raw_path=planner_result.raw_path,
                    notes="meta-action",
                    loop_trigger=loop_trigger,
                    stop_reason=f"meta_{action.get('action')}",
                    stop_details=None,
                )
                self.trace.write(record)
                step_records.append(record)
                print(f"[loop] Meta action {action.get('action')}, stopping loop.")
                stop_reason = f"meta_{action.get('action')}"
                stop_details = None
                self.text_log.write(f"[{step_id}] meta action {action.get('action')} -> stop")
                break

            decision = analyze_action(action, observation)
            allowed = not decision.requires_confirmation
            if decision.requires_confirmation:
                allowed = prompt_confirmation(action, decision.reason, auto_confirm=self.settings.auto_confirm)
                if allowed:
                    print("[loop] Action confirmed by user.")
                else:
                    print("[loop] Action rejected by user, stopping loop.")
                    record = StepRecord(
                        step=step,
                        session_id=session_id,
                        step_id=step_id,
                        action=action,
                        planner_retries=planner_result.retries_used,
                        security=decision,
                        execute_success=None,
                        execute_error="Rejected by user",
                        observation=observation,
                        exec_result_path=None,
                        planner_raw_path=planner_result.raw_path,
                        notes="rejected",
                        loop_trigger=loop_trigger,
                        stop_reason="rejected_by_user",
                        stop_details=decision.reason,
                    )
                    self.trace.write(record)
                    step_records.append(record)
                    stop_reason = "rejected_by_user"
                    stop_details = decision.reason
                    break

            exec_result_path = None
            exec_success = None
            exec_error = None

            if self.execute_enabled:
                try:
                    try:
                        exec_result, new_obs = await asyncio.wait_for(
                            execute_with_fallbacks(
                                page,
                                self.settings,
                                action,
                                observation,
                                max_reobserve_attempts=1,
                                observation_label=step_id,
                            ),
                            timeout=self.settings.execute_timeout_sec,
                        )
                    except Exception as exc:
                        if not self.runtime.is_target_closed_error(exc):
                            raise
                        self.text_log.write(f"[{step_id}] TargetClosed detected; retrying execute on new page")
                        # Reacquire a live page and retry once.
                        page = await self._ensure_page()
                        exec_result, new_obs = await asyncio.wait_for(
                            execute_with_fallbacks(
                                page,
                                self.settings,
                                action,
                                observation,
                                max_reobserve_attempts=1,
                                observation_label=step_id,
                            ),
                            timeout=self.settings.execute_timeout_sec,
                        )
                    exec_result_path = save_execution_result(exec_result, self.settings.paths.state_dir, label=step_id)
                    exec_success = exec_result.success
                    exec_error = exec_result.error
                    observation = new_obs
                    self.agent_state.add_observation(new_obs)
                    status = "success" if exec_result.success else "failed"
                    print(f"[loop] Execute {status}; result saved to {exec_result_path}")
                    self.text_log.write(f"[{step_id}] execute {status} action={action} err={exec_error}")
                except asyncio.TimeoutError:
                    exec_success = False
                    exec_error = "Execute timeout"
                    stop_reason = "execute_timeout"
                    stop_details = f"step={step_id}"
                    print(f"[loop] Execute timeout at step {step}.")
                    self.text_log.write(f"[{step_id}] execute timeout; stopping loop")
                    record = StepRecord(
                        step=step,
                        session_id=session_id,
                        step_id=step_id,
                        action=action,
                        planner_retries=planner_result.retries_used if 'planner_result' in locals() else 0,
                        security=decision,
                        execute_success=exec_success,
                        execute_error=exec_error,
                        observation=observation,
                        exec_result_path=None,
                        planner_raw_path=planner_result.raw_path if 'planner_result' in locals() else None,
                        notes="execute_timeout",
                        loop_trigger=loop_trigger,
                        stop_reason=stop_reason,
                        stop_details=stop_details,
                    )
                    self.trace.write(record)
                    step_records.append(record)
                    break
                except Exception as exc:
                    exec_success = False
                    exec_error = str(exc)
                    print(f"[loop] Execute failed at step {step}: {exc}")
                    self.text_log.write(f"[{step_id}] execute failed: {exc}")
            else:
                print("[loop] Execute disabled, skipping action execution.")
                exec_success = None
                exec_error = "Execution disabled"
                self.text_log.write(f"[{step_id}] execute disabled")

            record = StepRecord(
                step=step,
                session_id=session_id,
                step_id=step_id,
                action=action,
                planner_retries=planner_result.retries_used,
                security=decision,
                execute_success=exec_success,
                execute_error=exec_error,
                observation=observation,
                exec_result_path=exec_result_path,
                planner_raw_path=planner_result.raw_path,
                notes="",
                loop_trigger=loop_trigger,
            )
            self.trace.write(record)
            step_records.append(record)

            # Track action history with change signals
            prev_url_for_action = prev_observation_for_progress.url if prev_observation_for_progress else None
            url_changed_flag = prev_observation_for_progress and prev_observation_for_progress.url != observation.url
            prev_hash_for_action = self._mapping_hash(prev_observation_for_progress)
            curr_hash_for_action = self._mapping_hash(observation)
            dom_changed_flag = (
                prev_hash_for_action is not None and curr_hash_for_action is not None and prev_hash_for_action != curr_hash_for_action
            )
            self.action_history.append(
                {
                    "action": action.get("action"),
                    "element_id": action.get("element_id"),
                    "url": observation.url,
                    "prev_url": prev_url_for_action,
                    "url_changed": bool(url_changed_flag),
                    "dom_changed": bool(dom_changed_flag),
                }
            )

            # Track repeated execution failures per element to avoid them in planner input.
            elem_id_for_fail = action.get("element_id")
            if exec_success is False and elem_id_for_fail is not None:
                key = str(elem_id_for_fail)
                self.exec_fail_counts[key] = self.exec_fail_counts.get(key, 0) + 1
                if self.exec_fail_counts[key] >= 2:
                    self.avoid_elements.add(key)
                    self.text_log.write(f"[{step_id}] added element {key} to avoid list due to repeated failures")
            elif exec_success and elem_id_for_fail is not None:
                self.exec_fail_counts.pop(str(elem_id_for_fail), None)

            if exec_success is False:
                # Failed execution: continue to next iteration to replan with updated observation (if any)
                self.last_error_context = exec_error
                continue
            else:
                self.last_error_context = None

            # Proceed to next step with fresh observation
            setattr(page, "_hide_overlay", self.settings.hide_overlay)
            observation = await self._capture_with_retry(page, label=f"{step_id}-post")
            self.agent_state.add_observation(observation)
            self._log_zone_counts(f"[{step_id}] post-exec", observation)

            # Progress detector (always on): decide whether to stop or ask user
            progress_action, progress_score, evidence = self._decide_progress_stop(
                goal,
                prev_observation_for_progress,
                observation,
                action,
            )
            if progress_action:
                self.text_log.write(
                    f"[{step_id}] progress score={progress_score} evidence={evidence} action={progress_action['action']}"
                )
                print(f"[loop] Progress score={progress_score}; evidence={evidence}; proposing {progress_action['action']}.")
                if progress_action["action"] == "ask_user":
                    reply = input("[loop] Looks like goal may be done. Stop? (y/N): ").strip().lower()
                    if reply not in {"y", "yes"}:
                        # User wants to continue
                        self.repeat_count = 0
                        self.stagnation_count = 0
                        self.auto_scrolls_used = 0
                        continue

                meta_step_id = generate_step_id(f"{session_id}-progress")
                meta_record = StepRecord(
                    step=step + 1,
                    session_id=session_id,
                    step_id=meta_step_id,
                    action=progress_action,
                    planner_retries=0,
                    security=SecurityDecision(False, None),
                    execute_success=True,
                    execute_error=None,
                    observation=observation,
                    exec_result_path=None,
                    planner_raw_path=None,
                    notes=f"auto-progress score={progress_score} evidence={evidence}",
                    loop_trigger=None,
                    stop_reason=f"progress_{progress_action['action']}",
                    stop_details=f"score={progress_score}, evidence={evidence}",
                )
                self.trace.write(meta_record)
                step_records.append(meta_record)
                self.text_log.write(
                    f"[{meta_step_id}] stopping on progress action={progress_action['action']} "
                    f"score={progress_score} evidence={evidence}"
                )
                stop_reason = f"progress_{progress_action['action']}"
                stop_details = f"score={progress_score}, evidence={evidence}"
                break

            # Track repeats (action + element + url)
            sig = (action.get("action"), action.get("element_id"), observation.url)
            if sig == self.last_action_sig:
                self.repeat_count += 1
            else:
                self.repeat_count = 0
                self.last_action_sig = sig

            # Track visited urls/elements counts
            url = observation.url
            self.visited_urls[url] = self.visited_urls.get(url, 0) + 1
            elem_id = action.get("element_id")
            if elem_id is not None:
                key = str(elem_id)
                self.visited_elements[key] = self.visited_elements.get(key, 0) + 1

        summary = self._write_summary(session_id, step_records, observation, stop_reason, stop_details)
        print(
            f"[loop] Finished. reason={summary.get('stop_reason')} "
            f"details={summary.get('stop_details')} "
            f"last_url={summary.get('last_url')} progress={summary.get('last_progress_score')} "
            f"evidence={summary.get('last_progress_evidence')}"
        )
        self.text_log.write(
            f"[session {session_id}] finished reason={summary.get('stop_reason')} "
            f"details={summary.get('stop_details')} url={summary.get('last_url')} "
            f"progress={summary.get('last_progress_score')} evidence={summary.get('last_progress_evidence')}"
        )

    def _write_summary(
        self,
        session_id: str,
        records: list[StepRecord],
        last_observation: Observation,
        stop_reason: Optional[str] = None,
        stop_details: Optional[str] = None,
    ) -> dict[str, Any]:
        success = sum(1 for r in records if r.execute_success)
        failed = sum(1 for r in records if r.execute_success is False)
        rejected = sum(1 for r in records if r.notes == "rejected")
        meta = sum(1 for r in records if r.notes == "meta-action")
        summary = {
            "session_id": session_id,
            "steps": len(records),
            "execute_success": success,
            "execute_failed": failed,
            "rejected": rejected,
            "meta": meta,
            "last_url": last_observation.url,
            "last_screenshot": str(last_observation.screenshot_path),
            "last_observation_recorded_at": last_observation.recorded_at,
            "last_progress_score": self.last_progress_score,
            "last_progress_evidence": self.last_progress_evidence,
            "stop_reason": stop_reason,
            "stop_details": stop_details,
        }
        summary_path = self.settings.paths.logs_dir / "summary.json"
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        with summary_path.open("w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        self.text_log.write(f"[session {session_id}] summary: {summary}")
        try:
            self.trace.write({"summary": summary, "session_id": session_id})
        except Exception:
            pass
        return summary
