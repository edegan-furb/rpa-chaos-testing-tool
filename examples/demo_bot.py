import time
from typing import Callable


def eventually(fn: Callable[[], None], timeout_s: float = 8.0, interval_s: float = 0.25, label: str = ""):
    """
    Retries fn until it stops raising or timeout is reached.
    Use for chaos-tolerant steps.
    """
    end = time.time() + timeout_s
    last_err = None
    while time.time() < end:
        try:
            fn()
            return
        except Exception as e:
            last_err = e
            time.sleep(interval_s)
    msg = f"Step failed after {timeout_s}s"
    if label:
        msg += f" ({label})"
    raise AssertionError(msg) from last_err


def run(page):
    page.set_default_timeout(5_000)
    page.set_default_navigation_timeout(20_000)

    # Open app
    eventually(
        lambda: page.goto("https://demo.playwright.dev/todomvc/", wait_until="domcontentloaded"),
        timeout_s=15,
        label="goto todomvc",
    )

    # Input locator
    todo = page.get_by_placeholder("What needs to be done?")

    items = ["buy milk", "write chaos tool", "fix flaky bot"]

    # Add items robustly: after Enter, verify the row appeared
    for text in items:
        def add_one():
            todo.click()
            todo.fill(text)
            todo.press("Enter")
            assert page.get_by_text(text).count() == 1, f"Item not created: {text}"

        eventually(add_one, timeout_s=10, interval_s=0.3, label=f"add item: {text}")

    # Toggle first item to completed, then verify completed count
    def toggle_completed():
        row = page.get_by_text("buy milk").locator("..")
        row.get_by_role("checkbox").click()
        assert page.locator("li.completed").count() == 1, "Expected 1 completed item"

    eventually(toggle_completed, timeout_s=10, interval_s=0.3, label="toggle completed")

    # Filters can be disrupted by modals; retry and assert correct visibility
    def go_active_and_check():
        page.get_by_role("link", name="Active").click()
        assert page.get_by_text("buy milk").count() == 0, "Completed item should be hidden in Active"
        assert page.get_by_text("write chaos tool").count() == 1, "Active item missing in Active"

    eventually(go_active_and_check, timeout_s=10, interval_s=0.3, label="filter Active")

    def go_completed_and_check():
        page.get_by_role("link", name="Completed").click()
        assert page.get_by_text("buy milk").count() == 1, "Completed item should show in Completed"
        assert page.get_by_text("write chaos tool").count() == 0, "Active item should be hidden in Completed"

    eventually(go_completed_and_check, timeout_s=10, interval_s=0.3, label="filter Completed")

    def go_all_and_check():
        page.get_by_role("link", name="All").click()
        for text in items:
            assert page.get_by_text(text).count() == 1, f"Expected item missing in All: {text}"

    eventually(go_all_and_check, timeout_s=10, interval_s=0.3, label="filter All")

    # Optional: clear completed if button exists; verify completed removed
    def clear_completed_if_present():
        btn = page.get_by_role("button", name="Clear completed")
        if btn.count() == 0:
            return
        btn.click()
        assert page.locator("li.completed").count() == 0, "Completed items not cleared"

    eventually(clear_completed_if_present, timeout_s=8, interval_s=0.3, label="clear completed (optional)")
