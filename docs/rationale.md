Rationale and Choices
=====================

Why Playwright headful persistent
---------------------------------
- Visible browser for debugging/demos, matches task requirements.
- Persistent context allows manual login and session continuity.
- Headful reduces surprises vs headless (layout/visibility).

Why Set-of-Mark (DOM overlay) instead of CV
-------------------------------------------
- Lightweight, no CV stack; low CPU/GPU requirements.
- Direct element IDs (data-agent-id) for reliable execution.
- Token-efficient: send limited mapping + optional small screenshot.

Why LangGraph
-------------
- Declarative flow with nodes/edges, retries, interrupts, recursion_limit.
- Easier to extend (AskUser/ErrorRetry/LoopMitigation) vs ad-hoc loop.
- Better tracing and termination guarantees (terminal_reason invariant).

Safety Model
------------
- Destructive heuristics (keywords, card patterns, sensitive forms, risky domains).
- Confirm gate (auto_confirm toggle).
- Stop reasons recorded; meta actions filtered by stage to avoid premature stops.

Token/Context Strategy
----------------------
- Mapping_limit + zone balancing + goal-aware candidate scoring.
- Include screenshot on small mapping or errors; avoid giant payloads.
- Allowed_actions constrain planner choices; avoid_search/search_no_change signals reduce loops.

Anti-loop/Progress
------------------
- Hashes (URL/DOM/candidates) to detect frozen state; loop_mitigation paged scans.
- Budget-based terminals (no_progress_steps, planner_calls, max_steps).
- Stage_not_advanced triggers insufficient_knowledge instead of spinning.

Trade-offs / Boundaries
-----------------------
- No automated tab switching by URL/title (only switch_tab action/hint).
- No HOME/SEARCH_FORM page types; listing/detail heuristic only.
- Legacy loop retained but frozen; all focus on LangGraph.
- No test harness/mock page yet.
