"""First-run (Out-of-the-box) experience for ``ruyi``."""

import sys
from typing import Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from ..config import GlobalConfig


class OOBE:
    """Out-of-the-box experience (OOBE) handler for RuyiSDK CLI."""

    def __init__(self, gc: "GlobalConfig") -> None:
        self._gc = gc
        self.handlers: list[Callable[[], None]] = []

    def is_first_run(self) -> bool:
        if tm := self._gc.telemetry:
            return tm.is_first_run
        # cannot reliably determine first run status without telemetry
        # we may revisit this later if it turns out users want OOBE tips even
        # if they know how to disable telemetry (hence more likely to be power
        # users)
        return False

    def should_prompt(self) -> bool:
        return self.is_first_run() and sys.stdin.isatty()

    def maybe_prompt(self) -> None:
        if not self.should_prompt():
            return

        logger = self._gc.logger
        logger.I(
            "Welcome to RuyiSDK! This appears to be your first run of [yellow]ruyi[/].",
        )

        for handler in self.handlers:
            handler()
