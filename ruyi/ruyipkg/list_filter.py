import argparse
import enum
from typing import Any, Callable, Iterable, NamedTuple, Sequence, TypeVar, TYPE_CHECKING

from ..cli.completion import ArgcompleteAction
from ..utils.global_mode import TRUTHY_ENV_VAR_VALUES

if TYPE_CHECKING:
    from ..config import GlobalConfig
    from .repo import MetadataRepo

_T = TypeVar("_T")


class ListFilterOpKind(enum.Enum):
    UNKNOWN = 0
    CATEGORY_CONTAINS = 1
    CATEGORY_IS = 2
    NAME_CONTAINS = 3
    RELATED_TO_ENTITY = 4
    IS_INSTALLED = 5


class ListFilterOp(NamedTuple):
    op: ListFilterOpKind
    arg: str


class ListFilterExecCtx(NamedTuple):
    cfg: "GlobalConfig"
    mr: "MetadataRepo"
    category: str
    pkg_name: str


def _execute_filter_op(op: ListFilterOp, ctx: ListFilterExecCtx) -> bool:
    match op.op:
        case ListFilterOpKind.CATEGORY_CONTAINS:
            return op.arg in ctx.category
        case ListFilterOpKind.CATEGORY_IS:
            return op.arg == ctx.category
        case ListFilterOpKind.NAME_CONTAINS:
            return op.arg in ctx.pkg_name
        case ListFilterOpKind.RELATED_TO_ENTITY:
            es = ctx.mr.entity_store
            return es.is_entity_related_to(
                f"pkg:{ctx.category}/{ctx.pkg_name}",
                op.arg,
                transitive=True,
                unidirectional=False,
            )
        case ListFilterOpKind.IS_INSTALLED:
            asks_for_installed = op.arg.lower() in TRUTHY_ENV_VAR_VALUES

            # We need to check all versions of this package to see if any are installed
            # For now, we'll use a simple heuristic - check if ANY version is installed
            installed_packages = ctx.cfg.ruyipkg_global_state.list_installed_packages()
            is_installed = any(
                pkg.category == ctx.category and pkg.name == ctx.pkg_name
                for pkg in installed_packages
            )
            return not (is_installed ^ asks_for_installed)
        case _:
            return False


class ListFilter:
    def __init__(self) -> None:
        self.ops: list[ListFilterOp] = []

    def __bool__(self) -> bool:
        return len(self.ops) > 0

    def __repr__(self) -> str:
        return f"<ListFilter ops={self.ops!r}>"

    def append(self, op: ListFilterOp) -> None:
        self.ops.append(op)

    def check_pkg_name(
        self,
        cfg: "GlobalConfig",
        mr: "MetadataRepo",
        category: str,
        pkg_name: str,
    ) -> bool:
        ctx = ListFilterExecCtx(cfg, mr, category, pkg_name)
        return all(_execute_filter_op(op, ctx) for op in self.ops)


class ListFilterAction(ArgcompleteAction):
    def __init__(
        self,
        option_strings: Sequence[str],
        dest: str,
        nargs: int | str | None = None,
        const: _T | None = None,
        default: _T | str | None = None,
        type: Callable[[str], _T] | argparse.FileType | None = None,
        choices: Iterable[_T] | None = None,
        required: bool = False,
        help: str | None = None,
        metavar: str | tuple[str, ...] | None = None,
    ) -> None:
        # for now let's just support unary filter ops
        if nargs != 1:
            raise ValueError("nargs != 1 not supported")
        if const is not None:
            raise ValueError("const not supported")
        if default is not None:
            raise ValueError("default not supported")
        if type is not None:
            raise ValueError("type not supported")
        if choices is not None:
            raise ValueError("choices not supported")
        if required:
            raise ValueError("required not supported")
        if metavar is None:
            metavar = "STR"

        super().__init__(
            option_strings,
            dest,
            nargs,
            const,
            default,
            type,
            choices,
            required,
            help,
            metavar,
        )

        self.filter_op_kind: ListFilterOpKind
        match option_strings[0].lstrip("-"):
            case "category-contains":
                self.filter_op_kind = ListFilterOpKind.CATEGORY_CONTAINS
            case "category-is":
                self.filter_op_kind = ListFilterOpKind.CATEGORY_IS
            case "name-contains":
                self.filter_op_kind = ListFilterOpKind.NAME_CONTAINS
            case "related-to-entity":
                self.filter_op_kind = ListFilterOpKind.RELATED_TO_ENTITY
            case "is-installed":
                self.filter_op_kind = ListFilterOpKind.IS_INSTALLED
            case _:
                # should never happen
                self.filter_op_kind = ListFilterOpKind.UNKNOWN

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: str | Sequence[Any] | None,
        option_string: str | None = None,
    ) -> None:
        dest: ListFilter | None = getattr(namespace, self.dest, None)
        if not dest:
            dest = ListFilter()
            setattr(namespace, self.dest, dest)

        val: str
        if isinstance(values, str):
            val = values
        elif isinstance(values, list):
            val = values[0]
        else:
            # should never happen
            # XXX: no easy way to wire to the global logger instance here
            # log.D(f"unexpected values type: {type(values)}")
            val = ""

        dest.append(ListFilterOp(self.filter_op_kind, val))
