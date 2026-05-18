import dataclasses
import enum
import pathlib
import tomllib
from typing import Iterable, Literal, NotRequired, Sequence

import tomlkit
from tomlkit.exceptions import ParseError

from ..utils.porcelain import PorcelainEntity, PorcelainEntityType
from .canonical_dump import dumps_canonical_package_manifest_toml
from .host import get_native_host
from .list_filter import ListFilter, ListFilterOp, ListFilterOpKind
from .pkg_manifest import PackageManifest
from .repo import RepoConfig

try:
    from semver.version import Version  # type: ignore[import-untyped,unused-ignore]
except ModuleNotFoundError:
    from semver import VersionInfo as Version  # type: ignore[import-untyped,unused-ignore]


CheckName = Literal["format", "parse"]
CheckSet = frozenset[CheckName]

DEFAULT_CHECKS: CheckSet = frozenset(("format", "parse"))

CHECK_FORMAT: CheckName = "format"
CHECK_PARSE: CheckName = "parse"


class CheckSeverity(enum.StrEnum):
    ERROR = "error"
    WARNING = "warning"


class CheckUsageError(ValueError):
    pass


class CheckDiagnosticPorcelain(PorcelainEntity, total=False):
    severity: str
    code: str
    check: str
    path: str
    message: str
    line: NotRequired[int]
    column: NotRequired[int]
    hint: NotRequired[str]


@dataclasses.dataclass(frozen=True)
class CheckDiagnostic:
    severity: CheckSeverity
    code: str
    check: str
    path: pathlib.Path
    message: str
    line: int | None = None
    column: int | None = None
    hint: str | None = None

    def to_porcelain(self) -> CheckDiagnosticPorcelain:
        result: CheckDiagnosticPorcelain = {
            "ty": PorcelainEntityType.CheckDiagnosticV1,
            "severity": self.severity.value,
            "code": self.code,
            "check": self.check,
            "path": str(self.path),
            "message": self.message,
        }
        if self.line is not None:
            result["line"] = self.line
        if self.column is not None:
            result["column"] = self.column
        if self.hint is not None:
            result["hint"] = self.hint
        return result


@dataclasses.dataclass(frozen=True)
class ManifestRepoContext:
    repo_root: pathlib.Path
    manifest_root_name: str
    category: str
    name: str
    version: str


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


def infer_manifest_repo_context(path: pathlib.Path) -> ManifestRepoContext | None:
    if len(path.parents) < 4:
        return None

    manifest_root = path.parents[2]
    if manifest_root.name not in ("packages", "manifests"):
        return None

    return ManifestRepoContext(
        repo_root=path.parents[3],
        manifest_root_name=manifest_root.name,
        category=path.parents[1].name,
        name=path.parent.name,
        version=path.stem,
    )


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


def check_manifest_file(
    path: pathlib.Path,
    checks: CheckSet = DEFAULT_CHECKS,
) -> list[CheckDiagnostic]:
    diagnostics: list[CheckDiagnostic] = []

    text = _read_manifest_text(path, diagnostics)
    if text is None:
        return diagnostics

    manifest = _parse_manifest_text(path, text, diagnostics)
    if manifest is None:
        return diagnostics

    if CHECK_PARSE in checks:
        diagnostics.extend(_check_manifest_parse_surface(path, manifest))
        if diagnostics:
            return diagnostics

    if CHECK_FORMAT in checks:
        diagnostics.extend(_check_manifest_format(path, text, manifest))

    return diagnostics


def check_repo(
    repo_root: pathlib.Path,
    checks: CheckSet = DEFAULT_CHECKS,
    package_selector: ListFilter | None = None,
) -> list[CheckDiagnostic]:
    diagnostics = check_repo_config(repo_root)

    manifest_root = _find_manifest_root(repo_root)
    if manifest_root is None:
        return diagnostics

    for path in sorted(p for p in manifest_root.rglob("*") if p.is_file()):
        rel_path = path.relative_to(manifest_root)
        parts = rel_path.parts
        identity = _package_identity_from_manifest_relpath(parts)

        if (
            package_selector is not None
            and identity is not None
            and not _package_selector_matches(package_selector, *identity)
        ):
            continue

        path_diagnostic = _check_repo_manifest_path(path, rel_path, parts)
        if path_diagnostic is not None:
            diagnostics.append(path_diagnostic)
            continue

        diagnostics.extend(check_manifest_file(path, checks))

    return diagnostics


def check_repo_config(repo_root: pathlib.Path) -> list[CheckDiagnostic]:
    path = repo_root / "config.toml"
    try:
        with open(path, "rb") as fp:
            obj = tomllib.load(fp)
    except FileNotFoundError:
        return [
            _diagnostic(
                "RYC0005",
                CHECK_PARSE,
                path,
                "config.toml is missing",
            )
        ]
    except tomllib.TOMLDecodeError as exc:
        return [
            _diagnostic(
                "RYC0005",
                CHECK_PARSE,
                path,
                str(exc),
                line=getattr(exc, "lineno", None),
                column=getattr(exc, "colno", None),
            )
        ]
    except (OSError, UnicodeDecodeError) as exc:
        return [
            _diagnostic(
                "RYC0005",
                CHECK_PARSE,
                path,
                str(exc),
            )
        ]

    try:
        RepoConfig.from_object(obj)
    except (KeyError, TypeError, ValueError, RuntimeError) as exc:
        return [
            _diagnostic(
                "RYC0005",
                CHECK_PARSE,
                path,
                _format_manifest_error(exc),
            )
        ]
    return []


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


def _read_manifest_text(
    path: pathlib.Path,
    diagnostics: list[CheckDiagnostic],
) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        diagnostics.append(
            _diagnostic(
                "RYC0002",
                CHECK_PARSE,
                path,
                str(exc),
            )
        )
        return None


def _parse_manifest_text(
    path: pathlib.Path,
    text: str,
    diagnostics: list[CheckDiagnostic],
) -> PackageManifest | None:
    try:
        doc = tomlkit.loads(text)
    except ParseError as exc:
        diagnostics.append(
            _diagnostic(
                "RYC0002",
                CHECK_PARSE,
                path,
                str(exc),
                line=getattr(exc, "line", None),
                column=getattr(exc, "col", None),
            )
        )
        return None
    except ValueError as exc:
        diagnostics.append(
            _diagnostic(
                "RYC0002",
                CHECK_PARSE,
                path,
                str(exc),
            )
        )
        return None

    try:
        return PackageManifest(doc)
    except (KeyError, TypeError, ValueError, RuntimeError) as exc:
        diagnostics.append(
            _diagnostic(
                "RYC0003",
                CHECK_PARSE,
                path,
                _format_manifest_error(exc),
            )
        )
        return None


def _check_manifest_parse_surface(
    path: pathlib.Path,
    manifest: PackageManifest,
) -> list[CheckDiagnostic]:
    try:
        _touch_manifest_parse_surface(manifest)
    except (KeyError, TypeError, ValueError, RuntimeError) as exc:
        return [
            _diagnostic(
                "RYC0003",
                CHECK_PARSE,
                path,
                _format_manifest_error(exc),
            )
        ]
    return []


def _check_manifest_format(
    path: pathlib.Path,
    text: str,
    manifest: PackageManifest,
) -> list[CheckDiagnostic]:
    try:
        canonical_text = dumps_canonical_package_manifest_toml(manifest)
    except (KeyError, TypeError, ValueError, RuntimeError) as exc:
        return [
            _diagnostic(
                "RYC0003",
                CHECK_FORMAT,
                path,
                _format_manifest_error(exc),
            )
        ]

    if text == canonical_text:
        return []

    return [
        _diagnostic(
            "RYC0001",
            CHECK_FORMAT,
            path,
            "manifest is not canonical",
            hint=f"run: ruyi admin format-manifest {path}",
        )
    ]


def _touch_manifest_parse_surface(manifest: PackageManifest) -> None:
    manifest.to_raw()
    manifest.raw_doc
    manifest.slug
    manifest.kind
    manifest.desc
    manifest.doc_uri
    manifest.vendor_name
    manifest.upstream_version

    service_level = manifest.service_level
    service_level.level
    service_level.has_known_issues
    list(service_level.known_issues)

    for distfile in manifest.distfiles.values():
        distfile.name
        distfile.urls
        distfile.size
        distfile.checksums
        distfile.prefixes_to_unpack
        distfile.strip_components
        distfile.unpack_method
        distfile.fetch_restriction
        distfile.get_checksum("sha256")
        distfile.is_restricted("fetch")
        distfile.is_restricted("mirror")

    if binary_metadata := manifest.binary_metadata:
        binary_metadata.data
        binary_metadata.is_available_for_current_host
        for host in binary_metadata.data:
            binary_metadata.get_distfile_names_for_host(host)
            binary_metadata.get_commands_for_host(host)

    if blob_metadata := manifest.blob_metadata:
        blob_metadata.get_distfile_names()

    native_host = get_native_host()
    if source_metadata := manifest.source_metadata:
        source_metadata.get_distfile_names_for_host(native_host)

    if toolchain_metadata := manifest.toolchain_metadata:
        toolchain_metadata.target
        toolchain_metadata.target_arch
        toolchain_metadata.quirks
        toolchain_metadata.has_quirk("default")
        toolchain_metadata.satisfies_quirk_set(set())
        list(toolchain_metadata.components)
        toolchain_metadata.get_component_version("gcc")
        toolchain_metadata.has_binutils
        toolchain_metadata.has_clang
        toolchain_metadata.has_gcc
        toolchain_metadata.has_llvm
        toolchain_metadata.included_sysroot

    if emulator_metadata := manifest.emulator_metadata:
        emulator_metadata.quirks
        for program in emulator_metadata.programs:
            program.relative_path
            program.flavor
            program.supported_arches
            program.binfmt_misc
            program.is_qemu
        list(emulator_metadata.list_for_arch(native_host.arch))

    if provisionable_metadata := manifest.provisionable_metadata:
        provisionable_metadata.partition_map
        provisionable_metadata.strategy


def _find_manifest_root(repo_root: pathlib.Path) -> pathlib.Path | None:
    for name in ("packages", "manifests"):
        manifest_root = repo_root / name
        if manifest_root.is_dir():
            return manifest_root
    return None


def _package_identity_from_manifest_relpath(
    parts: tuple[str, ...],
) -> tuple[str, str] | None:
    if len(parts) < 2:
        return None
    return parts[0], parts[1]


def _package_selector_matches(
    package_selector: ListFilter,
    category: str,
    pkg_name: str,
) -> bool:
    for op in package_selector.ops:
        match op.op:
            case ListFilterOpKind.ALL:
                continue
            case ListFilterOpKind.CATEGORY_CONTAINS:
                if op.arg not in category:
                    return False
            case ListFilterOpKind.CATEGORY_IS:
                if op.arg != category:
                    return False
            case ListFilterOpKind.NAME_CONTAINS:
                if op.arg not in pkg_name:
                    return False
            case ListFilterOpKind.RELATED_TO_ENTITY | ListFilterOpKind.IS_INSTALLED:
                raise CheckUsageError(
                    "stateful package selectors are not supported by admin check"
                )
            case _:
                raise CheckUsageError("unknown package selector")
    return True


def _check_repo_manifest_path(
    path: pathlib.Path,
    rel_path: pathlib.Path,
    parts: tuple[str, ...],
) -> CheckDiagnostic | None:
    if len(parts) != 3:
        return _diagnostic(
            "RYC0004",
            CHECK_PARSE,
            path,
            f"manifest path must be <category>/<name>/<version>.toml, got {rel_path}",
        )

    if path.suffix.lower() != ".toml":
        return _diagnostic(
            "RYC0004",
            CHECK_PARSE,
            path,
            "manifest file must use the .toml extension",
        )

    version = path.stem
    try:
        Version.parse(version)
    except ValueError as exc:
        return _diagnostic(
            "RYC0004",
            CHECK_PARSE,
            path,
            f"manifest filename is not a valid semantic version: {version}: {exc}",
        )
    return None


def _diagnostic(
    code: str,
    check: CheckName,
    path: pathlib.Path,
    message: str,
    *,
    line: int | None = None,
    column: int | None = None,
    hint: str | None = None,
) -> CheckDiagnostic:
    return CheckDiagnostic(
        severity=CheckSeverity.ERROR,
        code=code,
        check=check,
        path=path,
        message=message,
        line=line,
        column=column,
        hint=hint,
    )


def _format_manifest_error(exc: BaseException) -> str:
    if isinstance(exc, KeyError):
        return f"missing package manifest field: {exc!s}"
    message = str(exc)
    return message if message else exc.__class__.__name__
