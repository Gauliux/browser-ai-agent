User Interaction Modes
======================

CLI Mode
--------
- Run `python src/main.py --goal "..."` (LangGraph default; add flags as needed).
- If no goal provided, prompts for goal and keeps browser open.
- clean-between-goals option wipes logs/state/screenshots between goals (profile intact).
- INTERACTIVE_PROMPTS controls whether agent asks questions (default off).

UI Shell Mode
-------------
- `python src/main.py --ui-shell` (optional flags).
- Features: saves interrupted goal, simple wait animation, prompts for confirmation on ask_user in interactive mode.
- ui_step_limit can override max_steps for UI shell runs only.

Confirmations & Prompts
-----------------------
- Safety confirm: triggered on destructive heuristics or risky navigation; auto_confirm bypasses prompt.
- Progress ask_user: only on later stages (locate/verify); in non-interactive mode sets stop_reason without blocking; in interactive mode asks user.
- Ask_user node: same interactive/non-interactive behavior controlled by INTERACTIVE_PROMPTS.

- Flags Commonly Used
--------------------
- --plan-only / --auto-confirm
- --langgraph (always on by default; legacy only as fallback)
- --hide-overlay / --observe-screenshot-mode
- --paged-scan-steps / --paged-scan-viewports / --conservative-observe
- --max-steps / --max-planner-calls / --max-no-progress-steps
- --max-reobserve-attempts / --max-attempts-per-element / --scroll-step
- --mapping-limit / --loop thresholds / --auto-done-*

Logs & Artifacts (user-facing)
------------------------------
- Browser profile: data/user_data (persistent).
- Screenshots: data/screenshots (observe-*, exec-*, js-click/text-click) with session/step labels.
- State: data/state (observation-*, planner-*, execute-*) JSON with session/step labels.
- logs/agent.log — text log; logs/trace.jsonl — structured trace (if enabled).

What to Expect
--------------
- Headful browser opens; overlays may be visible unless hidden.
- LangGraph loop prints progress evidence and summary; final stop_reason shown in console.
- If INTERACTIVE_PROMPTS=false, agent will not wait for terminal input (except safety confirm unless auto_confirm).*** End Patch
