"""
helper functions for CLI completions

see https://github.com/kislyuk/argcomplete/issues/443 for why this is needed
"""

import argparse
from typing import Any, Callable, Final, Optional, Sequence, cast

SUPPORTED_SHELLS: Final[set[str]] = {"bash", "zsh"}


class ArgcompleteAction(argparse.Action):
    completer: Optional[Callable[[str, object], list[str]]]

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: str | Sequence[Any] | None,
        option_string: str | None = None,
    ) -> None:
        raise NotImplementedError(".__call__() not defined")


class ArgumentParser(argparse.ArgumentParser):
    def add_argument(self, *args: Any, **kwargs: Any) -> ArgcompleteAction:
        return cast(ArgcompleteAction, super().add_argument(*args, **kwargs))
