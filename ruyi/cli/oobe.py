"""First-run (Out-of-the-box) experience for ``ruyi``."""

import os
import sys
from typing import Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from ..config import GlobalConfig


SHELL_AUTO_COMPLETION_TIP = """
[bold green]tip[/]: you can enable shell auto-completion for [yellow]ruyi[/] by adding the
following line to your [green]{shrc}[/], if you have not done so already:

    [green]eval "$(ruyi --output-completion-script={shell})"[/]

You can do so by running the following command later:

    [green]echo 'eval "$(ruyi --output-completion-script={shell})"' >> {shrc}[/]
"""


class OOBE:
    """Out-of-the-box experience (OOBE) handler for RuyiSDK CLI."""

    def __init__(self, gc: "GlobalConfig") -> None:
        self._gc = gc
        self.handlers: list[Callable[[], None]] = [
            self._builtin_shell_completion_tip,
        ]

    def is_first_run(self) -> bool:
        if tm := self._gc.telemetry:
            return tm.is_first_run
        # cannot reliably determine first run status without telemetry
        # we may revisit this later if it turns out users want OOBE tips even
        # if they know how to disable telemetry (hence more likely to be power
        # users)
        return False

    def should_prompt(self) -> bool:
        from ..utils.global_mode import is_env_var_truthy

        if not sys.stdin.isatty() or not sys.stdout.isatty():
            # This is of higher priority than even the debug override, because
            # we don't want to mess up non-interactive sessions even in case of
            # debugging.
            return False

        if is_env_var_truthy(os.environ, "RUYI_DEBUG_FORCE_FIRST_RUN"):
            return True

        return self.is_first_run()

    def maybe_prompt(self) -> None:
        if not self.should_prompt():
            return

        logger = self._gc.logger
        logger.I(
            "Welcome to RuyiSDK! This appears to be your first run of [yellow]ruyi[/].",
        )

        for handler in self.handlers:
            handler()

    def _builtin_shell_completion_tip(self) -> None:
        from ..utils.node_info import probe_for_shell
        from .completion import SUPPORTED_SHELLS

        # Only show the tip if we're not externally managed by a package manager,
        # because we expect proper shell integration to be done by distro packagers
        if self._gc.is_installation_externally_managed:
            return

        shell = probe_for_shell(os.environ)
        if shell not in SUPPORTED_SHELLS:
            return

        self._gc.logger.stdout(
            SHELL_AUTO_COMPLETION_TIP.format(
                shell=shell,
                shrc=f"~/.{shell}rc",
            )
        )
