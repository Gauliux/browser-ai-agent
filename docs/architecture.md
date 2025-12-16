Architecture Overview
=====================

Goal
----
Headful, persistent Playwright agent orchestrated by LangGraph that plans via OpenAI function-calling, observes the page with a lightweight DOM overlay (Set-of-Mark), executes actions with fallbacks, and enforces safety/confirmation for risky operations.

Key Decisions
-------------
- Stack: Python 3, Playwright (headful, persistent context), OpenAI SDK (function-calling), LangGraph for orchestration.
- Context control: Set-of-Mark DOM annotation instead of CV; mapping limited and zone-balanced; optional screenshot only when needed.
- Orchestration: LangGraph state graph with explicit nodes (observe → loop_mitigation → goal_check → planner → safety/confirm → execute → progress → ask_user/error_retry).
- Safety: Heuristics for destructive actions, confirm gate (auto-confirm optional).
- Persistence: User profile via launch_persistent_context; artifacts/logs saved per session/step.
- FSM + terminals: Monotonic stages (orient/context/locate/verify/done) and explicit terminal reasons (goal_satisfied, goal_failed, loop_stuck, budget_exhausted).

Main Components
---------------
- Runtime: Browser lifecycle, active page tracking, TargetClosed resilience.
- Observe: DOM annotation, overlay badges, mapping pruning/balancing, optional screenshot, paged_scan.
- Planner: LLM call with strict schema, structured context (page_type, explore_mode, allowed_actions, avoid_search, candidates, errors, loop flags).
- Execute: Action executor with fallbacks (reobserve, JS click, text-match), limits per element, unified artifacts.
- Safety: Destructive heuristics and confirmation prompts.
- Loop mitigation: Paged scans and conservative observe when loop detected.
- Progress & Termination: Progress scoring, ask_user gating (interactive optional), goal_check for terminals, no_progress/loop_stuck logic with hashes.

Flows
-----
- LangGraph loop: observe → (loop_mitigation if loop) → goal_check (terminals) → planner (LLM) → safety/confirm → execute → progress → ask_user/non-interactive end → observe.
- Error handling: planner/execute timeouts/errors → error_retry node (one retry) → observe.
- Terminals: goal_satisfied, goal_failed (insufficient_knowledge/stage_not_advanced/planner_call budget), loop_stuck (world frozen + budget), budget_exhausted (max_steps/recursion).

