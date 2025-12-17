import argparse
import asyncio
import os
import shutil
from dataclasses import replace

from agent.config.config import Settings
from agent.core.planner import Planner
from agent.infra.runtime import BrowserRuntime
from agent.io.ui_shell import run_ui_shell
from agent.legacy.loop import AgentLoop
from agent.legacy.state import AgentState


async def amain() -> None:
    parser = argparse.ArgumentParser(description="Headful browser agent with planning and execution.")
    parser.add_argument("--goal", help="Goal for the agent (overrides PLANNER_GOAL).")
    parser.add_argument("--goals", nargs="+", help="Multiple goals to run sequentially.")
    parser.add_argument("--execute", action="store_true", help="Enable execution (overrides EXECUTE env).")
    parser.add_argument("--auto-confirm", action="store_true", help="Auto-confirm destructive actions.")
    parser.add_argument("--max-steps", type=int, help="Max steps in the loop.")
    parser.add_argument("--planner-timeout", type=float, help="Planner timeout in seconds.")
    parser.add_argument("--execute-timeout", type=float, help="Execute timeout in seconds.")
    parser.add_argument("--screenshot-mode", choices=["auto", "always", "never"], help="Planner screenshot mode.")
    parser.add_argument("--mapping-limit", type=int, help="Limit of elements sent to planner.")
    parser.add_argument("--loop-repeat-threshold", type=int, help="Repeats before loop mitigation triggers.")
    parser.add_argument("--stagnation-threshold", type=int, help="Stagnation threshold for loop mitigation.")
    parser.add_argument("--max-auto-scrolls", type=int, help="Max auto-scroll attempts during loop mitigation.")
    parser.add_argument("--loop-retry-mapping-boost", type=int, help="Extra mapping size on loop replan.")
    parser.add_argument("--langgraph", action="store_true", help="Use LangGraph orchestrator instead of custom loop.")
    parser.add_argument("--hide-overlay", action="store_true", help="Hide overlay badges during observation.")
    parser.add_argument("--paged-scan-steps", type=int, help="Number of paged scan steps during loop mitigation.")
    parser.add_argument("--paged-scan-viewports", type=int, help="How many viewports to capture per paged scan step.")
    parser.add_argument("--auto-done-mode", choices=["auto", "ask"], help="Auto-done mode.")
    parser.add_argument("--auto-done-threshold", type=int, help="Progress score threshold.")
    parser.add_argument(
        "--auto-done-require-url-change",
        action="store_true",
        help="Require URL change for auto-done decisions.",
    )
    parser.add_argument(
        "--observe-screenshot-mode",
        choices=["on_demand", "always"],
        help="Screenshot mode during observation.",
    )
    parser.add_argument(
        "--sync-viewport",
        action="store_true",
        help="Enable syncing viewport size with window.innerWidth/innerHeight during observation.",
    )
    parser.add_argument(
        "--no-sync-viewport",
        action="store_true",
        help="Disable syncing viewport size with window.innerWidth/innerHeight during observation.",
    )
    parser.add_argument(
        "--clean-between-goals",
        action="store_true",
        help="Clean logs/state/screenshots between goals (persistent profile remains).",
    )
    parser.add_argument(
        "--ui-shell",
        action="store_true",
        help="Enable optional UI shell wrapper (interactive supervisor) instead of default CLI loop.",
    )
    parser.add_argument(
        "--ui-step-limit",
        type=int,
        help="Step limit for UI shell runs (overrides max_steps for that mode only).",
    )
    parser.add_argument(
        "--conservative-observe",
        action="store_true",
        help="Perform an extra observe pass before scrolling/paged scan when loop is detected.",
    )
    parser.add_argument(
        "--max-reobserve-attempts",
        type=int,
        help="Max reobserve attempts during execute fallbacks.",
    )
    parser.add_argument(
        "--max-attempts-per-element",
        type=int,
        help="Max allowed failed attempts per element before avoid.",
    )
    parser.add_argument(
        "--scroll-step",
        type=int,
        help="Scroll step size in pixels for scroll actions and fallbacks.",
    )
    args = parser.parse_args()

    settings = Settings.load()

    def apply_cli_overrides() -> None:
        # Centralized override block for CLI/interactive extensions.
        if args.execute:
            os.environ["EXECUTE"] = "1"
        if args.auto_confirm:
            settings.auto_confirm = True
        if args.max_steps:
            settings.max_steps = max(1, args.max_steps)
        if args.planner_timeout:
            settings.planner_timeout_sec = max(0.1, args.planner_timeout)
        if args.execute_timeout:
            settings.execute_timeout_sec = max(0.1, args.execute_timeout)
        if args.screenshot_mode:
            settings.planner_screenshot_mode = args.screenshot_mode
        if args.mapping_limit:
            settings.mapping_limit = max(1, args.mapping_limit)
        if args.loop_repeat_threshold:
            settings.loop_repeat_threshold = max(1, args.loop_repeat_threshold)
        if args.stagnation_threshold:
            settings.stagnation_threshold = max(1, args.stagnation_threshold)
        if args.max_auto_scrolls:
            settings.max_auto_scrolls = max(1, args.max_auto_scrolls)
        if args.loop_retry_mapping_boost is not None:
            settings.loop_retry_mapping_boost = max(0, args.loop_retry_mapping_boost)
        if args.hide_overlay:
            settings.hide_overlay = True
        if args.paged_scan_steps:
            settings.paged_scan_steps = max(1, args.paged_scan_steps)
        if args.paged_scan_viewports:
            settings.paged_scan_viewports = max(1, args.paged_scan_viewports)
        if args.auto_done_mode:
            settings.auto_done_mode = args.auto_done_mode
        if args.auto_done_threshold:
            settings.auto_done_threshold = max(1, args.auto_done_threshold)
        if args.auto_done_require_url_change:
            settings.auto_done_require_url_change = True
        if args.observe_screenshot_mode:
            settings.observe_screenshot_mode = args.observe_screenshot_mode
        if args.sync_viewport:
            settings.sync_viewport_with_window = True
        if args.no_sync_viewport:
            settings.sync_viewport_with_window = False
        if args.conservative_observe:
            settings.conservative_observe = True
        if args.max_reobserve_attempts:
            settings.max_reobserve_attempts = max(1, args.max_reobserve_attempts)
        if args.max_attempts_per_element:
            settings.max_attempts_per_element = max(1, args.max_attempts_per_element)
        if args.scroll_step:
            settings.scroll_step = max(50, args.scroll_step)

    apply_cli_overrides()

    # UI shell may want its own step limit without mutating base settings permanently.
    ui_settings = replace(settings)
    if args.ui_step_limit:
        ui_settings.max_steps = max(1, args.ui_step_limit)

    goals_queue = []
    if args.goals:
        goals_queue.extend(args.goals)
    elif args.goal:
        goals_queue.append(args.goal)
    use_langgraph = args.langgraph or os.getenv("USE_LANGGRAPH", "").lower() in {"1", "true", "yes", "on"}
    runtime = BrowserRuntime(ui_settings if args.ui_shell else settings)

    await runtime.launch()
    page = await runtime.ensure_page()
    print(f"[agent] Headful browser started with persistent profile at: {ui_settings.paths.user_data_dir if args.ui_shell else settings.paths.user_data_dir}")
    print(f"[agent] Initial URL: {page.url}")
    print(f"[agent] Trace/logs: {ui_settings.paths.logs_dir if args.ui_shell else settings.paths.logs_dir}")

    def clean_between_goals() -> None:
        if not args.clean_between_goals:
            return
        active_paths = ui_settings.paths if args.ui_shell else settings.paths
        for folder in [active_paths.logs_dir, active_paths.state_dir, active_paths.screenshots_dir]:
            try:
                shutil.rmtree(folder, ignore_errors=True)
            except Exception:
                pass
        active_paths.ensure()

    def prompt_goal() -> str:
        return input("Enter goal for the agent (leave blank to stop): ").strip()

    if not settings.openai_api_key:
        print("[agent] OPENAI_API_KEY not set; skipping loop and keeping browser open.")
    else:
        execute_flag = os.getenv("EXECUTE", "").lower() in {"1", "true", "yes", "on"}
        planner = Planner(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            base_url=settings.openai_base_url,
        )
        active_settings = ui_settings if args.ui_shell else settings

        # Interactive-first: if no goals provided, start interactive loop without default execution.
        if args.ui_shell:
            # Build runner (prefer LangGraph; fallback to legacy loop wrapper).
            runner = None
            text_log = None
            trace = None
            if use_langgraph:
                try:
                    from agent.langgraph_loop import build_graph
                    from agent.infra.tracing import TextLogger, TraceLogger

                    text_log = TextLogger(active_settings.paths.logs_dir / "agent.log")
                    trace = TraceLogger(active_settings.paths.logs_dir / "trace.jsonl")
                    runner = build_graph(
                        settings=active_settings,
                        planner=planner,
                        runtime=runtime,
                        execute_enabled=execute_flag,
                        text_log=text_log,
                        trace=trace,
                    )
                except Exception as exc:
                    print(f"[agent] Failed to init LangGraph loop for UI shell: {exc}. Falling back to legacy runner.")
                    use_langgraph = False
            if runner is None:
                agent_state = AgentState()
                loop = AgentLoop(
                    settings=active_settings,
                    planner=planner,
                    agent_state=agent_state,
                    execute_enabled=execute_flag,
                    runtime=runtime,
                )

                async def legacy_runner(goal: str) -> dict[str, object]:
                    await loop.run(goal=goal)
                    return {"stop_reason": None, "stop_details": None}

                runner = legacy_runner

            await run_ui_shell(
                runner=runner,
                settings=active_settings,
                clean_between_goals=clean_between_goals,
                text_log=text_log,
                trace=trace,
            )
        else:
            while True:
                if goals_queue:
                    goal = goals_queue.pop(0)
                else:
                    goal = prompt_goal()
                if not goal:
                    print("[agent] No goal provided; keeping browser open.")
                    break
                print(f"[agent] Starting goal: {goal}")
                clean_between_goals()
                if use_langgraph:
                    try:
                        from agent.langgraph_loop import build_graph
                    except Exception as exc:
                        print(f"[agent] Failed to init LangGraph loop: {exc}. Falling back to custom loop.")
                        use_langgraph = False

                if use_langgraph:
                    text_log = None
                    trace = None
                    try:
                        from agent.infra.tracing import TextLogger, TraceLogger

                        text_log = TextLogger(active_settings.paths.logs_dir / "agent.log")
                        trace = TraceLogger(active_settings.paths.logs_dir / "trace.jsonl")
                    except Exception:
                        pass
                    runner = build_graph(
                        settings=active_settings,
                        planner=planner,
                        runtime=runtime,
                        execute_enabled=execute_flag,
                        text_log=text_log,
                        trace=trace,
                    )
                    result_state = await runner(goal=goal)  # type: ignore[arg-type]
                    print(
                        f"[agent] LangGraph finished. reason={result_state.get('stop_reason')} "
                        f"url={result_state.get('observation').url if result_state.get('observation') else None}"
                    )
                else:
                    agent_state = AgentState()
                    loop = AgentLoop(
                        settings=active_settings,
                        planner=planner,
                        agent_state=agent_state,
                        execute_enabled=execute_flag,
                        runtime=runtime,
                    )
                    await loop.run(goal=goal)

    print("[agent] Press Ctrl+C to stop the runtime when you are done observing (browser will close automatically).")

    try:
        await runtime.idle()
    except KeyboardInterrupt:
        print("\n[agent] Interrupt received, shutting down...")
    finally:
        await runtime.close()
        print("[agent] Browser closed. Bye.")


if __name__ == "__main__":
    asyncio.run(amain())
