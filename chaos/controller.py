from __future__ import annotations

import random
from typing import Iterable

from chaos.experiments import ChaosContext, Experiment


class ChaosController:
    def __init__(self, experiments: list[Experiment], seed: int):
        self.experiments = experiments
        self.ctx = ChaosContext(random.Random(seed))

    def on_start(self, page, browser_context) -> None:
        for e in self.experiments:
            e.on_start(self.ctx, page, browser_context)

    def before_action(self, page, action: str, args, kwargs) -> None:
        for e in self.experiments:
            e.before_action(self.ctx, page, action, args, kwargs)

    def after_action(self, page, action: str, args, kwargs) -> None:
        for e in self.experiments:
            e.after_action(self.ctx, page, action, args, kwargs)
