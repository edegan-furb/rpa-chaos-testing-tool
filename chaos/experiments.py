from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Optional, Callable, Dict, Any


@dataclass
class ChaosEvent:
    kind: str
    detail: Dict[str, Any]


class ChaosContext:
    def __init__(self, rng: random.Random):
        self.rng = rng
        self.events: list[ChaosEvent] = []

    def emit(self, kind: str, **detail: Any) -> None:
        self.events.append(ChaosEvent(kind=kind, detail=detail))


class Experiment:
    """Interface for chaos experiments."""
    name: str = "experiment"

    def before_action(self, ctx: ChaosContext, page, action: str, args, kwargs) -> None:
        pass

    def after_action(self, ctx: ChaosContext, page, action: str, args, kwargs) -> None:
        pass

    def on_start(self, ctx: ChaosContext, page, browser_context) -> None:
        pass


class RandomDelay(Experiment):
    name = "random_delay"

    def __init__(self, min_s: float, max_s: float, probability: float = 1.0):
        self.min_s = min_s
        self.max_s = max_s
        self.p = probability

    def before_action(self, ctx: ChaosContext, page, action: str, args, kwargs) -> None:
        if ctx.rng.random() <= self.p:
            d = ctx.rng.uniform(self.min_s, self.max_s)
            ctx.emit(self.name, action=action, delay_s=round(d, 3))
            time.sleep(d)


class ModalOverlay(Experiment):
    name = "modal_overlay"

    def __init__(self, probability: float = 0.25, min_ms: int = 800, max_ms: int = 2500):
        self.p = probability
        self.min_ms = min_ms
        self.max_ms = max_ms

    def before_action(self, ctx: ChaosContext, page, action: str, args, kwargs) -> None:
        # Inject only sometimes, and mostly around clicks / fills to simulate annoying UI
        if action not in ("click", "fill", "type", "press"):
            return
        if ctx.rng.random() > self.p:
            return

        dur_ms = ctx.rng.randint(self.min_ms, self.max_ms)
        ctx.emit(self.name, action=action, duration_ms=dur_ms)

        js = """
        (durMs) => {
          const existing = document.getElementById("__rpa_chaos_modal__");
          if (existing) existing.remove();

          const overlay = document.createElement("div");
          overlay.id = "__rpa_chaos_modal__";
          overlay.style.position = "fixed";
          overlay.style.inset = "0";
          overlay.style.zIndex = "2147483647";
          overlay.style.background = "rgba(0,0,0,0.35)";
          overlay.style.display = "flex";
          overlay.style.alignItems = "center";
          overlay.style.justifyContent = "center";

          const box = document.createElement("div");
          box.style.width = "min(520px, 92vw)";
          box.style.background = "white";
          box.style.borderRadius = "14px";
          box.style.padding = "18px";
          box.style.boxShadow = "0 20px 50px rgba(0,0,0,0.25)";
          box.innerHTML = `
            <div style="font-family: Arial; font-weight: 700; font-size: 16px; margin-bottom: 8px;">
              Chaos modal
            </div>
            <div style="font-family: Arial; font-size: 13px; opacity: 0.85;">
              Simulated overlay blocking interaction.
            </div>
          `;

          overlay.appendChild(box);
          document.body.appendChild(overlay);

          setTimeout(() => {
            const el = document.getElementById("__rpa_chaos_modal__");
            if (el) el.remove();
          }, durMs);
        }
        """
        try:
            page.evaluate(js, dur_ms)
        except Exception:
            # If page isn't ready for eval, ignore this injection.
            pass


class NetworkChaos(Experiment):
    """
    Chromium-only: uses CDP to throttle network and optionally go offline briefly.
    """
    name = "network_chaos"

    def __init__(
        self,
        throttle_probability: float = 0.25,
        offline_probability: float = 0.10,
        latency_ms_min: int = 300,
        latency_ms_max: int = 1200,
        down_kbps_min: int = 200,
        down_kbps_max: int = 1500,
        up_kbps_min: int = 100,
        up_kbps_max: int = 800,
        offline_ms_min: int = 800,
        offline_ms_max: int = 2500,
    ):
        self.tp = throttle_probability
        self.op = offline_probability
        self.lat_min = latency_ms_min
        self.lat_max = latency_ms_max
        self.down_min = down_kbps_min
        self.down_max = down_kbps_max
        self.up_min = up_kbps_min
        self.up_max = up_kbps_max
        self.off_min = offline_ms_min
        self.off_max = offline_ms_max

        self._cdp = None

    def on_start(self, ctx: ChaosContext, page, browser_context) -> None:
        # Create CDP session (Chromium only)
        try:
            self._cdp = browser_context.new_cdp_session(page)
            self._cdp.send("Network.enable")
        except Exception:
            self._cdp = None

    def before_action(self, ctx: ChaosContext, page, action: str, args, kwargs) -> None:
        if self._cdp is None:
            return

        # Prefer to trigger around navigation to simulate real slowness
        if action not in ("goto", "click"):
            return

        r = ctx.rng.random()

        # Offline burst
        if r <= self.op:
            off_ms = ctx.rng.randint(self.off_min, self.off_max)
            ctx.emit(self.name, mode="offline_burst", duration_ms=off_ms, action=action)
            try:
                self._cdp.send(
                    "Network.emulateNetworkConditions",
                    {
                        "offline": True,
                        "latency": 0,
                        "downloadThroughput": -1,
                        "uploadThroughput": -1,
                    },
                )
                time.sleep(off_ms / 1000.0)
            finally:
                try:
                    self._cdp.send(
                        "Network.emulateNetworkConditions",
                        {
                            "offline": False,
                            "latency": 0,
                            "downloadThroughput": -1,
                            "uploadThroughput": -1,
                        },
                    )
                except Exception:
                    pass
            return

        # Throttle
        if r <= self.op + self.tp:
            latency = ctx.rng.randint(self.lat_min, self.lat_max)
            down_kbps = ctx.rng.randint(self.down_min, self.down_max)
            up_kbps = ctx.rng.randint(self.up_min, self.up_max)

            # CDP expects bytes/sec
            down_bps = int((down_kbps * 1024) / 8)
            up_bps = int((up_kbps * 1024) / 8)

            ctx.emit(
                self.name,
                mode="throttle",
                latency_ms=latency,
                down_kbps=down_kbps,
                up_kbps=up_kbps,
                action=action,
            )
            try:
                self._cdp.send(
                    "Network.emulateNetworkConditions",
                    {
                        "offline": False,
                        "latency": latency,
                        "downloadThroughput": down_bps,
                        "uploadThroughput": up_bps,
                    },
                )
            except Exception:
                pass
