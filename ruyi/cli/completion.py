"""
helper functions for CLI completions
"""

import argparse
from typing import cast, Callable, Optional, Protocol, Sequence, Any, TYPE_CHECKING

if TYPE_CHECKING:
    # A "lie" for type checking purposes. This is a known and wont fix issue for mypy.
    # Mypy would think the fallback import needs to be the same type as the first import.
    # See: https://github.com/python/mypy/issues/1153
    from argcomplete.completers import BaseCompleter
else:
    try:
        from argcomplete.completers import BaseCompleter
    except ImportError:
        # Fallback for environments where argcomplete is less than 2.0.0
        class BaseCompleter(object):
            def __call__(
                self,
                *,
                prefix: str,
                action: argparse.Action,
                parser: argparse.ArgumentParser,
                parsed_args: argparse.Namespace
            ) -> None:
                raise NotImplementedError(
                    "This method should be implemented by a subclass.")

if TYPE_CHECKING:
    from .. import config


class ArgcompleteAction(argparse.Action):
    # see https://github.com/kislyuk/argcomplete/issues/443 for why this typing is needed
    completer: Optional[Callable[[str, object], list[str]]]

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: str | Sequence[Any] | None,
        option_string: str | None = None,
    ) -> None:
        raise NotImplementedError('.__call__() not defined')


class ArgumentParser(argparse.ArgumentParser):
    def add_argument(self, *args: Any, **kwargs: Any) -> ArgcompleteAction:
        return cast(ArgcompleteAction, super().add_argument(*args, **kwargs))


class NoneCompleter(BaseCompleter):
    def __call__(self,
                 *,
                 prefix: str,
                 action: argparse.Action,
                 parser: argparse.ArgumentParser,
                 parsed_args: argparse.Namespace) -> None:
        return None


class DynamicCompleter(Protocol):
    def __call__(self, prefix: str, parsed_args: object,
                 **kwargs: Any) -> list[str]: ...


def package_completer_builder(
    cfg: "config.GlobalConfig",
    filters: list[Callable[[str], bool]] | None = None
) -> DynamicCompleter:
    # Lazy import to avoid circular dependency
    from ..ruyipkg.augmented_pkg import AugmentedPkg  # pylint: disable=import-outside-toplevel
    from ..ruyipkg.list_filter import ListFilter    # pylint: disable=import-outside-toplevel

    all_pkgs = list(AugmentedPkg.yield_from_repo(cfg, cfg.repo, ListFilter()))
    if filters is not None:
        all_pkgs = [
            pkg for pkg in all_pkgs
            if pkg.name is not None and
            all(f(pkg.name) for f in filters)
        ]

    def f(
        prefix: str,
        parsed_args: object,
        **kwargs: Any
    ) -> list[str]:
        return [
            pkg.name for pkg in all_pkgs
            if pkg.name is not None and
            pkg.name.startswith(prefix)
        ]

    return f
