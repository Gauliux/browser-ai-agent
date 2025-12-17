Module: src/agent/io/ui_shell.py
================================

Responsibility
--------------
- Опциональная интерактивная оболочка вокруг runner (предпочтительно LangGraph), обрабатывает ввод целей, прерывания и простые подсказки.

Behavior
--------
- run_ui_shell(runner, settings, clean_between_goals?, text_log?, trace?):
  - Сохраняет прерванную цель и предлагает повторить или ввести новую.
  - Показывает минимальную “ожидание” анимацию во время выполнения.
  - При KeyboardInterrupt/исключениях держит цикл живым и сохраняет goal для retry.
  - По завершении: если stop_reason мягкий (ask_user) и интерактив включён, спросит подтверждение; иначе пишет лог.
- Использует копию settings (replace) для UI-специфичных ограничений (ui_step_limit).

Inputs/Outputs
--------------
- runner: async goal -> dict (ожидается stop_reason/stop_details).
- clean_between_goals: опциональный callable; text_log/trace применяются если заданы.

Notes
-----
- INTERACTIVE_PROMPTS управляет тем, блокируют ли промпты; сама UI shell флаг не меняет.
