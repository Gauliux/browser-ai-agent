Module: src/agent/ui_shell.py
=============================

Responsibility
--------------
- Optional interactive supervisor shell around a runner (LangGraph preferred), handling goal input, interruptions, and simple prompts.

Behavior
--------
- run_ui_shell(runner, settings, clean_between_goals?, text_log?, trace?):
  - Stores interrupted goal (saved_goal) and offers to retry or enter new goal.
  - Shows minimal wait animation during runner execution.
  - On KeyboardInterrupt or exceptions, keeps loop alive and preserves goal for retry.
  - On completion: if stop_reason is a “soft” meta (ask_user) prompts for confirmation in interactive mode; otherwise logs result.
- Uses copy of settings (replace) for UI-specific tweaks (ui_settings passed in main).

Inputs/Outputs
--------------
- runner: async callable goal -> dict (stop_reason/stop_details expected).
- clean_between_goals: optional callable; text_log/trace used for logging if provided.

Notes
-----
- INTERACTIVE_PROMPTS env controls whether prompts block; UI shell itself does not override that flag.
