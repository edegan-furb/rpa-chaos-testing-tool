from __future__ import annotations

from typing import Any, Callable
from chaos.locator_proxy import LocatorProxy


class PageProxy:
    """
    Thin wrapper around Playwright `Page`.

    Why this exists:
    - We want chaos hooks to run before/after common actions.
    - Bots can keep writing normal Playwright code (`page.click(...)`,
      `page.get_by_role(...).click()`) while chaos is injected centrally.
    """
    def __init__(self, page, before_hook: Callable, after_hook: Callable):
        self._page = page
        self._before = before_hook
        self._after = after_hook

    # Intercept direct page actions
    def goto(self, *args, **kwargs):
        self._before("goto", args, kwargs)
        try:
            return self._page.goto(*args, **kwargs)
        finally:
            self._after("goto", args, kwargs)

    def click(self, *args, **kwargs):
        self._before("click", args, kwargs)
        try:
            return self._page.click(*args, **kwargs)
        finally:
            self._after("click", args, kwargs)

    def fill(self, *args, **kwargs):
        self._before("fill", args, kwargs)
        try:
            return self._page.fill(*args, **kwargs)
        finally:
            self._after("fill", args, kwargs)

    def type(self, *args, **kwargs):
        self._before("type", args, kwargs)
        try:
            return self._page.type(*args, **kwargs)
        finally:
            self._after("type", args, kwargs)

    def press(self, *args, **kwargs):
        self._before("press", args, kwargs)
        try:
            return self._page.press(*args, **kwargs)
        finally:
            self._after("press", args, kwargs)

    # Intercept locator getters (critical for get_by_role(...).click())
    def locator(self, *args, **kwargs):
        # Return a proxied Locator so nested actions also trigger hooks.
        loc = self._page.locator(*args, **kwargs)
        return LocatorProxy(loc, self._before, self._after)

    def get_by_role(self, *args, **kwargs):
        loc = self._page.get_by_role(*args, **kwargs)
        return LocatorProxy(loc, self._before, self._after)

    def get_by_text(self, *args, **kwargs):
        loc = self._page.get_by_text(*args, **kwargs)
        return LocatorProxy(loc, self._before, self._after)

    def get_by_label(self, *args, **kwargs):
        loc = self._page.get_by_label(*args, **kwargs)
        return LocatorProxy(loc, self._before, self._after)

    def __getattr__(self, name: str) -> Any:
        # Fallback: anything we don't explicitly wrap is delegated unchanged.
        return getattr(self._page, name)
