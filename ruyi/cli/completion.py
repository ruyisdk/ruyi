"""
helper functions for CLI completions
"""

from typing import Protocol, Callable

from ..config import GlobalConfig


class DynamicCompleter(Protocol):
    def __call__(self, prefix: str, parsed_args: object,
                 **kwargs) -> list[str]: ...


def package_completer_builder(
    cfg: GlobalConfig, filters: list[Callable[[str], bool]] | None = None
) -> DynamicCompleter:
    # Lazy import to avoid circular dependency
    from ..ruyipkg.pkg_cli import AugmentedPkg, ListFilter # pylint: disable=import-outside-toplevel

    all_pkgs = list(AugmentedPkg.yield_from_repo(cfg.repo, ListFilter()))
    if filters is not None:
        all_pkgs = [
            pkg for pkg in all_pkgs
            if pkg.name is not None and
            all(f(pkg.name) for f in filters)
        ]

    def f(
        prefix: str,
        parsed_args: object,
        **kwargs
    ):
        return [
            pkg.name for pkg in all_pkgs
            if pkg.name is not None and
            pkg.name.startswith(prefix)
        ]
    return f
