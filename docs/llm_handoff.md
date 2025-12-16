LLM Handoff (Quick Brief)
=========================

What This Agent Is
------------------
- Headful Playwright agent with persistent profile, orchestrated by LangGraph.
- Observes via DOM overlay (Set-of-Mark), plans via OpenAI function-calling, executes with fallbacks, enforces safety confirms.

Core Contract
-------------
- Actions: click | type | scroll | screenshot | navigate | search | go_back | go_forward | switch_tab | done | ask_user.
- FSM stages: orient → context → locate → verify; terminals: goal_satisfied | goal_failed | loop_stuck | budget_exhausted (always set).
- Safety: destructive heuristics + confirm (auto_confirm toggle); INTERACTIVE_PROMPTS controls user questions.

Key Behaviors
-------------
- Mapping limited, zone-balanced; goal-aware candidates extracted; optional screenshot on small/error cases.
- Planner context: page_type (listing/detail heuristic), explore_mode, allowed_actions by stage, avoid_search/search_no_change, candidates, loop/error/attempts.
- Execute fallbacks: reobserve (alt scroll) → JS click → text-match; per-element limits; TargetClosed retry.
- Loop handling: hashes for URL/DOM/candidates + repeat/stagnation/auto_scroll budgets; paged_scan mitigation.
- Progress: score/evidence; auto_done gated by stage; ask_user only on later stages; non-interactive by default.
- Termination invariant: every run ends with terminal_reason/type logged.

Configs to Know
---------------
- Flags/env: max_steps, mapping_limit, planner/execute timeouts, loop thresholds, max_planner_calls, max_no_progress_steps, max_reobserve_attempts, max_attempts_per_element, scroll_step, paged_scan_* , observe/planner screenshot modes, hide_overlay, auto_done_*, INTERACTIVE_PROMPTS, AUTO_CONFIRM, EXECUTE.
- Paths: data/user_data (profile), data/state (JSON artifacts), data/screenshots, logs/agent.log, logs/trace.jsonl.

Run Example
-----------
`python src/main.py --goal "..." --langgraph --execute --hide-overlay --mapping-limit 40 --max-steps 12`

Where to Look for Details
-------------------------
- architecture.md, agent_logic.md, configuration.md, browser_integration.md, modules/*.md for per-file detail, logging_artifacts.md for artifact formats.
