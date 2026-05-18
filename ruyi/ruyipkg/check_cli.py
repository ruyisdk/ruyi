import pathlib
from typing import Iterable, NotRequired, Sequence, TYPE_CHECKING

from .check import (
    CheckDiagnostic,
    CheckName,
    CheckSet,
    CheckSeverity,
    CheckUsageError,
    DEFAULT_CHECKS,
    CHECK_FORMAT,
    CHECK_PARSE,
    check_manifest_file,
    check_repo,
)
from .list_filter import ListFilter, ListFilterOp, ListFilterOpKind
from ..utils.porcelain import PorcelainEntity, PorcelainOutput

if TYPE_CHECKING:
    from ..config import GlobalConfig


class CheckDiagnosticPorcelain(PorcelainEntity, total=False):
    severity: str
    code: str
    check: str
    path: str
    message: str
    line: NotRequired[int]
    column: NotRequired[int]
    hint: NotRequired[str]


def normalize_checks(raw_checks: Iterable[str] | None) -> CheckSet:
    if raw_checks is None:
        return DEFAULT_CHECKS

    checks: set[CheckName] = set()
    for raw_check in raw_checks:
        match raw_check:
            case "format":
                checks.add(CHECK_FORMAT)
            case "parse":
                checks.add(CHECK_PARSE)
            case _:
                raise CheckUsageError(f"unsupported check: {raw_check}")
    return frozenset(checks) if checks else DEFAULT_CHECKS


def parse_package_selector_args(tokens: Sequence[str]) -> ListFilter:
    if not tokens:
        raise CheckUsageError("--only-packages requires at least one package selector")

    result = ListFilter()
    idx = 0
    unary_options = {
        "--category-contains": ListFilterOpKind.CATEGORY_CONTAINS,
        "--category-is": ListFilterOpKind.CATEGORY_IS,
        "--name-contains": ListFilterOpKind.NAME_CONTAINS,
    }
    unsupported_options = {"--is-installed", "--related-to-entity"}

    while idx < len(tokens):
        token = tokens[idx]
        option, sep, inline_value = token.partition("=")

        if option == "--all":
            if sep:
                raise CheckUsageError("--all does not take an argument")
            result.append(ListFilterOp(ListFilterOpKind.ALL, ""))
            idx += 1
            continue

        if option in unsupported_options:
            raise CheckUsageError(
                f"package selector {option} is not supported by admin check"
            )

        op_kind = unary_options.get(option)
        if op_kind is None:
            raise CheckUsageError(f"unsupported package selector: {token}")

        if sep:
            value = inline_value
        else:
            idx += 1
            if idx >= len(tokens):
                raise CheckUsageError(f"package selector {option} requires an argument")
            value = tokens[idx]
        result.append(ListFilterOp(op_kind, value))
        idx += 1

    return result


def format_check_diagnostic(diagnostic: CheckDiagnostic) -> str:
    location = str(diagnostic.path)
    if diagnostic.line is not None:
        location += f":{diagnostic.line}"
        if diagnostic.column is not None:
            location += f":{diagnostic.column}"

    result = (
        f"{location}: {diagnostic.severity.value} {diagnostic.code}: "
        f"{diagnostic.message}"
    )
    if diagnostic.hint is not None:
        result += f"\nhint: {diagnostic.hint}"
    return result


def count_diagnostics(
    diagnostics: Iterable[CheckDiagnostic],
) -> tuple[int, int]:
    errors = 0
    warnings = 0
    for diagnostic in diagnostics:
        match diagnostic.severity:
            case CheckSeverity.ERROR:
                errors += 1
            case CheckSeverity.WARNING:
                warnings += 1
    return errors, warnings


def format_check_summary(diagnostics: Iterable[CheckDiagnostic]) -> str:
    errors, warnings = count_diagnostics(diagnostics)
    return f"{errors} error(s), {warnings} warning(s)"


def has_error_diagnostic(diagnostics: Iterable[CheckDiagnostic]) -> bool:
    return any(diagnostic.severity == CheckSeverity.ERROR for diagnostic in diagnostics)


def do_admin_check(
    cfg: "GlobalConfig",
    *,
    files: Sequence[str] | None,
    repo: str | None,
    checks: Iterable[str] | None,
    only_packages: Sequence[str] | None,
) -> int:
    check_set = normalize_checks(checks)
    package_selector = (
        parse_package_selector_args(only_packages)
        if only_packages is not None
        else None
    )

    diagnostics: list[CheckDiagnostic] = []
    if repo is not None:
        diagnostics.extend(
            check_repo(
                pathlib.Path(repo),
                checks=check_set,
                package_selector=package_selector,
            )
        )
    else:
        if not files:
            raise CheckUsageError("either --file or --repo must be specified")
        for file in files:
            diagnostics.extend(check_manifest_file(pathlib.Path(file), check_set))

    if cfg.is_porcelain:
        with PorcelainOutput() as po:
            for diagnostic in diagnostics:
                po.emit(diagnostic.to_porcelain())
    else:
        for diagnostic in diagnostics:
            cfg.logger.stdout(format_check_diagnostic(diagnostic))
        cfg.logger.stdout(format_check_summary(diagnostics))

    return 1 if has_error_diagnostic(diagnostics) else 0
