Module: src/agent/io/ui_shell.py
================================

Responsibility
--------------
- Optional interactive shell around a runner (preferably LangGraph); handles goal input, interruptions, and simple prompts.

Behavior
--------
- run_ui_shell(runner, settings, clean_between_goals?, text_log?, trace?):
  - Saves an interrupted goal and offers to retry or enter a new one.
  - Shows a minimal “waiting” animation during execution.
  - On KeyboardInterrupt/errors keeps the loop alive and preserves the goal for retry.
  - On finish: if stop_reason is soft (ask_user) and interactive is on, asks for confirmation; otherwise logs.
- Uses a copy of settings (replace) for UI-specific limits (ui_step_limit).

Inputs/Outputs
--------------
- runner: async goal -> dict (expects stop_reason/stop_details).
- clean_between_goals: optional callable; text_log/trace used if provided.

Notes
-----
- INTERACTIVE_PROMPTS controls whether prompts block; the UI shell flag does not change it.
