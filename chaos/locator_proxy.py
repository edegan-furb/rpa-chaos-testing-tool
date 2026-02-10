from __future__ import annotations
from typing import Any, Callable


class LocatorProxy:
    """
    Thin wrapper around Playwright `Locator`.

    It mirrors locator actions and runs chaos hooks before/after each action.
    This lets experiments affect `page.get_by_...(...).click()` style flows too.
    """

    def __init__(self, locator, before_hook: Callable, after_hook: Callable):
        self._loc = locator
        self._before = before_hook
        self._after = after_hook

    def click(self, *args, **kwargs):
        self._before("click", args, kwargs)
        try:
            return self._loc.click(*args, **kwargs)
        finally:
            self._after("click", args, kwargs)

    def fill(self, *args, **kwargs):
        self._before("fill", args, kwargs)
        try:
            return self._loc.fill(*args, **kwargs)
        finally:
            self._after("fill", args, kwargs)

    def type(self, *args, **kwargs):
        self._before("type", args, kwargs)
        try:
            return self._loc.type(*args, **kwargs)
        finally:
            self._after("type", args, kwargs)

    def press(self, *args, **kwargs):
        self._before("press", args, kwargs)
        try:
            return self._loc.press(*args, **kwargs)
        finally:
            self._after("press", args, kwargs)

    def __getattr__(self, name: str) -> Any:
        # Delegate all non-intercepted Locator APIs unchanged.
        return getattr(self._loc, name)
