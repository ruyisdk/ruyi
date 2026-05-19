from typing import Any, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from ..cli.completer import DynamicCompleter
    from ..config import GlobalConfig


def repo_id_completer_builder(
    cfg: "GlobalConfig",
) -> "DynamicCompleter":
    repo_ids = [entry.id for entry in cfg.repo_entries]

    def f(prefix: str, parsed_args: object, **kwargs: Any) -> list[str]:
        return [rid for rid in repo_ids if rid.startswith(prefix)]

    return f


def package_completer_builder(
    cfg: "GlobalConfig",
    filters: list[Callable[[str], bool]] | None = None,
) -> "DynamicCompleter":
    pkg_names: list[str] | None = None

    def f(prefix: str, parsed_args: object, **kwargs: Any) -> list[str]:
        nonlocal pkg_names

        if pkg_names is None:
            # Lazy import to avoid circular dependency, and lazy repo access so
            # parser construction for unrelated completions does not sync repos.
            from ..ruyipkg.augmented_pkg import (
                AugmentedPkg,
            )  # pylint: disable=import-outside-toplevel
            from ..ruyipkg.list_filter import (
                ListFilter,
            )  # pylint: disable=import-outside-toplevel

            pkg_names = []
            for pkg in AugmentedPkg.yield_from_repo(cfg, cfg.repo, ListFilter()):
                if pkg.name is None:
                    continue
                if filters is not None and not all(fn(pkg.name) for fn in filters):
                    continue
                pkg_names.append(pkg.name)

        return [name for name in pkg_names if name.startswith(prefix)]

    return f
