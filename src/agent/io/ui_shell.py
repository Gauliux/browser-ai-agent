from __future__ import annotations

import sys
from dataclasses import replace
from typing import Any, Awaitable, Callable, Optional

from agent.config.config import Settings
from agent.core.graph_state import INTERACTIVE_PROMPTS
from agent.infra.tracing import TextLogger, TraceLogger


Runner = Callable[..., Awaitable[dict[str, Any]]]


async def run_ui_shell(
    *,
    runner: Runner,
    settings: Settings,
    clean_between_goals: Optional[Callable[[], None]] = None,
    text_log: Optional[TextLogger] = None,
    trace: Optional[TraceLogger] = None,
) -> None:
    """
    Lightweight UI shell wrapper around existing runner.
    Preserves default CLI; enabled explicitly via --ui-shell.
    """
    saved_goal: Optional[str] = None
    ui_settings = replace(settings)  # defensive copy if we tweak later
    interactive_prompts = INTERACTIVE_PROMPTS

    def log(msg: str) -> None:
        print(msg)
        if text_log:
            try:
                text_log.write(msg)
            except Exception:
                pass

    def wait_animation(prefix: str = "[ui] Исполнение") -> Callable[[bool], None]:
        # Returns a stepper that prints dots until stopped.
        dots = [".", "..", "...", "...."]
        state = {"i": 0, "active": False}

        def step(active: bool) -> None:
            if not active:
                if state["active"]:
                    sys.stdout.write("\r" + " " * (len(prefix) + 5) + "\r")
                    sys.stdout.flush()
                state["active"] = False
                return
            state["active"] = True
            sys.stdout.write("\r" + prefix + " " + dots[state["i"] % len(dots)])
            sys.stdout.flush()
            state["i"] += 1

        return step

    while True:
        print()  # spacer before prompt
        if saved_goal:
            user_input = input(
                f"[ui] Прерванная задача: \"{saved_goal}\"\n"
                f"[ui] Нажмите Enter для повторной попытки, либо опишите новую задачу ('выход' - для завершения сессии):"
            ).strip()
            if user_input.lower() == "выход":
                log("[ui] Выполняется завершение исполнения...")
                print()
                break
            goal = saved_goal if user_input == "" else user_input
        else:
            goal = input("[ui] Опишите задачу (оставтье поле пустым для выхода): ").strip()
            if not goal or goal.lower() == "выход":
                log("[ui] Запрошен выход.")
                break

        log("[ui] Исполнение...")
        if clean_between_goals:
            clean_between_goals()

        anim = wait_animation()
        try:
            # Simple waiting animation while runner executes
            anim(True)
            result = await runner(goal=goal)
            anim(False)
        except KeyboardInterrupt:
            anim(False)
            log("[ui] Ручное прерывание.")
            saved_goal = goal
            continue
        except Exception as exc:  # noqa: BLE001 - log and keep loop alive
            anim(False)
            log(f"[ui] Ошибка исполнения: {exc}")
            saved_goal = goal
            continue

        stop_reason = result.get("stop_reason") if isinstance(result, dict) else None
        stop_details = result.get("stop_details") if isinstance(result, dict) else None

        if stop_reason in {"planner_error", "planner_timeout", "execute_timeout", "rejected_by_user", "manual_stop", "error"}:
            log(f"[ui] Исполнение прервано: ({stop_reason})")
            saved_goal = goal
        else:
            if stop_reason in {"progress_ask_user", "meta_ask_user"}:
                if not interactive_prompts:
                    log("[ui] Агент завершил без интерактивного подтверждения (INTERACTIVE_PROMPTS=false).")
                    saved_goal = None
                else:
                    print()
                    ans = input("[ui] Агент считает задачу выполненной. Подтвердить завершение? (y/N): ").strip().lower()
                    if ans in {"y", "yes", "д", "да"}:
                        log("[ui] Завершено по подтверждению пользователя.")
                        saved_goal = None
                    else:
                        log("[ui] Отклонено. Задача сохранена для повторной попытки.")
                        saved_goal = goal
            else:
                log(f"[ui] Исполнение завершено. причина={stop_reason} подробности={stop_details}")
                saved_goal = None

        if trace:
            try:
                trace.write({"ui_shell": True, "goal": goal, "stop_reason": stop_reason, "stop_details": stop_details})
            except Exception:
                pass
