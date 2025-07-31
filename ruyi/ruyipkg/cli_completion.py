from typing import Any, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from ..cli.completer import DynamicCompleter
    from ..config import GlobalConfig


def package_completer_builder(
    cfg: "GlobalConfig",
    filters: list[Callable[[str], bool]] | None = None,
) -> "DynamicCompleter":
    # Lazy import to avoid circular dependency
    from ..ruyipkg.augmented_pkg import (
        AugmentedPkg,
    )  # pylint: disable=import-outside-toplevel
    from ..ruyipkg.list_filter import (
        ListFilter,
    )  # pylint: disable=import-outside-toplevel

    all_pkgs = list(
        AugmentedPkg.yield_from_repo(
            cfg,
            cfg.repo,
            ListFilter(),
            ensure_repo=False,
        )
    )
    if filters is not None:
        all_pkgs = [
            pkg
            for pkg in all_pkgs
            if pkg.name is not None and all(f(pkg.name) for f in filters)
        ]

    def f(prefix: str, parsed_args: object, **kwargs: Any) -> list[str]:
        return [
            pkg.name
            for pkg in all_pkgs
            if pkg.name is not None and pkg.name.startswith(prefix)
        ]

    return f
