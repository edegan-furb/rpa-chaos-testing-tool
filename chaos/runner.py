from __future__ import annotations

import importlib
import time
import traceback
from dataclasses import dataclass
from typing import Callable, Optional, Tuple

import typer
from rich.console import Console
from rich.table import Table
from playwright.sync_api import sync_playwright

# Typer creates a nice CLI automatically from functions and type hints.
# We disable shell-completion and also show help if the user runs the program with no args.
app = typer.Typer(add_completion=False, no_args_is_help=True)

# Rich Console is used for colored prints and tables (more readable than plain print()).
console = Console()


@dataclass
class RunResult:
    """
    Represents the result of ONE execution of the bot.
    We'll store it so we can calculate totals and show errors later.
    """
    idx: int                 # Which run number this was (1..N)
    ok: bool                 # True if the run completed without exception
    duration_ms: int         # How long the run took in milliseconds
    error: Optional[str] = None  # Full traceback string if it failed


def load_callable(target: str) -> Callable:
    """
    Loads a callable in the format: "package.module:function".
    Example: "examples.demo_bot:run"

    Why this exists:
    - We want to run ANY bot without changing this runner code.
    - So we pass where the bot function is via CLI: "module:function".
    """
    # Validate input format early so we fail fast with a clear message.
    if ":" not in target:
        raise ValueError('Target must be in the form "module:function" (e.g. examples.demo_bot:run)')

    # Split the string into the module part and the function part.
    module_name, func_name = target.split(":", 1)

    # Import the module dynamically (like "import examples.demo_bot").
    module = importlib.import_module(module_name)

    # Get the function from the module by name (like module.run).
    fn = getattr(module, func_name, None)

    # Make sure what we got is actually callable (a function, or a callable object).
    if fn is None or not callable(fn):
        raise ValueError(f'Function "{func_name}" not found or not callable in module "{module_name}"')

    return fn

def run_once(bot_fn, headless: bool, base_url: Optional[str], seed: int, chaos_enabled: bool):
    start = time.perf_counter()

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            context = browser.new_context()
            page = context.new_page()

            # ---- Chaos wiring ----
            from chaos.controller import ChaosController
            from chaos.page_proxy import PageProxy
            from chaos.experiments import RandomDelay, ModalOverlay, NetworkChaos

            if chaos_enabled:
                controller = ChaosController(
                    experiments=[
                        RandomDelay(min_s=0.05, max_s=0.60, probability=1.0),
                        ModalOverlay(probability=0.25, min_ms=700, max_ms=2200),
                        NetworkChaos(throttle_probability=0.25, offline_probability=0.10),
                    ],
                    seed=seed,
                )
                controller.on_start(page, context)

                chaos_page = PageProxy(
                    page,
                    before_hook=lambda action, args, kwargs: controller.before_action(page, action, args, kwargs),
                    after_hook=lambda action, args, kwargs: controller.after_action(page, action, args, kwargs),
                )
            else:
                controller = None
                chaos_page = page

            if base_url:
                chaos_page.goto(base_url)

            bot_fn(chaos_page)

            # Optional: return chaos events for reporting
            events = controller.ctx.events if controller else []

            context.close()
            browser.close()

        dur_ms = int((time.perf_counter() - start) * 1000)
        return True, dur_ms, None, events

    except Exception:
        dur_ms = int((time.perf_counter() - start) * 1000)
        err = traceback.format_exc(limit=20)
        return False, dur_ms, err, []


@app.command("run")
def run_cmd(
    target: str = typer.Argument(
        ...,
        help='Bot entrypoint in the format "module:function" (e.g. examples.demo_bot:run)',
    ),
    runs: int = typer.Option(
        5,
        "--runs",
        min=1,
        max=500,
        help="How many executions to perform",
    ),
    headless: bool = typer.Option(
        True,
        "--headless/--headed",
        help="Run headless (default) or show the browser",
    ),
    base_url: Optional[str] = typer.Option(
        None,
        "--base-url",
        help="Optional URL to open before calling the bot",
    ),
    seed: int = typer.Option(
        42,
        "--seed",
        help="Base seed for deterministic chaos (each run uses seed + run_index)",
    ),
    chaos: bool = typer.Option(
        True,
        "--chaos/--no-chaos",
        help="Enable or disable chaos injection",
    ),
):
    """
    Run a Playwright sync bot multiple times and report pass/fail + duration.
    """
    bot_fn = load_callable(target)

    results: list[RunResult] = []
    all_events = []  # optional: keep for future reporting

    for i in range(1, runs + 1):
        run_seed = seed + i  # different each run, still reproducible
        ok, dur_ms, err, events = run_once(
            bot_fn,
            headless=headless,
            base_url=base_url,
            seed=run_seed,
            chaos_enabled=chaos,
        )

        results.append(RunResult(idx=i, ok=ok, duration_ms=dur_ms, error=err))
        all_events.extend(events)

        status = "[green]OK[/green]" if ok else "[red]FAIL[/red]"
        chaos_tag = "[dim]chaos[/dim]" if chaos else "[dim]no-chaos[/dim]"
        console.print(f"Run {i}/{runs}: {status} ({dur_ms} ms) {chaos_tag} seed={run_seed} events={len(events)}")

    total = len(results)
    failures = [r for r in results if not r.ok]
    passed = total - len(failures)
    avg = int(sum(r.duration_ms for r in results) / total)

    table = Table(title="RPA Chaos - Report")
    table.add_column("Metric", style="bold")
    table.add_column("Value")

    table.add_row("Target", target)
    table.add_row("Runs", str(total))
    table.add_row("Passed", str(passed))
    table.add_row("Failed", str(len(failures)))
    table.add_row("Avg duration", f"{avg} ms")
    table.add_row("Chaos enabled", "Yes" if chaos else "No")
    table.add_row("Base seed", str(seed))
    table.add_row("Total chaos events", str(len(all_events)))

    console.print()
    console.print(table)

    if failures:
        console.print("\n[bold red]Failures (first 1 shown):[/bold red]\n")
        first = failures[0]
        console.print(f"[red]Run #{first.idx} failed[/red] after {first.duration_ms} ms\n")
        console.print(first.error)



# Standard Python entrypoint so this file can be run directly:
#   python runner.py run examples.demo_bot:run
if __name__ == "__main__":
    app()
