# examples/demo_bot_shitty.py
# Intentionally fragile bot: no retries, short timeouts, fixed sleeps, weak selectors.
# Designed to break under chaos.

import time

def run(page):
    page.set_default_timeout(1500)
    page.set_default_navigation_timeout(3000)

    # Fast navigate
    page.goto("https://demo.playwright.dev/todomvc/", wait_until="domcontentloaded")

    todo = page.get_by_placeholder("What needs to be done?")

    # Fixed sleeps (chaos + sleeps = pain)
    todo.click()
    time.sleep(0.05)
    todo.fill("write chaos tool")
    time.sleep(0.05)
    todo.press("Enter")

    # Immediately click filters with no verification
    time.sleep(0.05)
    page.get_by_role("link", name="Active").click()
    time.sleep(0.05)
    page.get_by_role("link", name="Completed").click()
    time.sleep(0.05)
    page.get_by_role("link", name="All").click()

    # Brittle assertion (will often fail under modal/delay/network chaos)
    assert page.get_by_text("write chaos tool").count() == 1, "Item missing (expected under chaos)"
