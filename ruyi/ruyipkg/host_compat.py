"""Host compatibility reporting for user-facing package workflows.

The ELF ABI checker is the first and currently only compatibility aspect.
This module owns the user-facing status vocabulary, the porcelain shape, and
the sidecar/probe session shared by `ruyi list` and `ruyi install`.
"""

from __future__ import annotations

import enum
import pathlib
from typing import Mapping, NamedTuple, Sequence, TypedDict, cast

from ..i18n import DeferredI18nString, _
from ..log import RuyiLogger
from .abi import (
    ABIReport,
    ABIScanError,
    DEFAULT_MAX_SIDECAR_BYTES,
    ElfABIRecord,
    load_abi_report_toml,
)
from .abi.aggregate import build_summary
from .abi.compat import check_host_compatibility
from .abi.hostprobe import HostABIProber
from .host import RuyiHost, canonicalize_host_str, get_native_host
from .pkg_manifest import BoundPackageManifest


class HostCompatStatus(enum.StrEnum):
    Unchecked = "unchecked"
    NoABIInfo = "no-abi-info"
    LikelyCompatible = "likely-compatible"
    LikelyIncompatible = "likely-incompatible"
    CompatibilityUnknown = "compatibility-unknown"

    def as_rich_markup(self) -> str:
        match self:
            case HostCompatStatus.Unchecked:
                return _("unchecked")
            case HostCompatStatus.NoABIInfo:
                return _("[dim]no ABI info[/]")
            case HostCompatStatus.LikelyCompatible:
                return _("[green]likely compatible[/]")
            case HostCompatStatus.LikelyIncompatible:
                return _("[red]likely incompatible[/]")
            case HostCompatStatus.CompatibilityUnknown:
                return _("[yellow]compatibility unknown[/]")
        return ""


class HostCompatProblem(NamedTuple):
    check: str
    compatible: bool | None
    msgid: str
    params: Mapping[str, object]


class PorcelainHostCompatProblemV1(TypedDict):
    check: str
    compatible: bool | None
    msgid: str
    params: dict[str, object]


class PorcelainHostCompatV1(TypedDict):
    status: str
    problems: list[PorcelainHostCompatProblemV1]


class PackageHostCompat:
    def __init__(
        self,
        status: HostCompatStatus,
        problems: Sequence[HostCompatProblem] = (),
        sidecars: Sequence[pathlib.Path] = (),
    ) -> None:
        self.status = status
        self.problems = tuple(problems)
        self.sidecars = tuple(sidecars)

    def to_porcelain(self) -> PorcelainHostCompatV1:
        return {
            "status": self.status.value,
            "problems": [
                {
                    "check": problem.check,
                    "compatible": problem.compatible,
                    "msgid": problem.msgid,
                    "params": dict(problem.params),
                }
                for problem in self.problems
            ],
        }


def format_problem(problem: HostCompatProblem) -> str:
    message = _(cast(DeferredI18nString, problem.msgid)).format(**problem.params)
    return _("{check}: {message}").format(check=problem.check, message=message)


class HostCompatChecker:
    def __init__(
        self,
        *,
        logger: RuyiLogger,
        refresh_resolver: bool = True,
        prober: HostABIProber | None = None,
    ) -> None:
        self._logger = logger
        self._prober = prober or HostABIProber(
            logger=logger,
            refresh_resolver=refresh_resolver,
        )
        self._sidecars: dict[pathlib.Path, ABIReport | None] = {}

    def check(
        self,
        pm: BoundPackageManifest,
        host: str | RuyiHost,
        *,
        allow_probing: bool,
    ) -> PackageHostCompat:
        if not allow_probing:
            return PackageHostCompat(HostCompatStatus.Unchecked)

        if canonicalize_host_str(host) != str(get_native_host()):
            return PackageHostCompat(HostCompatStatus.Unchecked)

        bm = pm.binary_metadata
        if bm is None:
            return PackageHostCompat(HostCompatStatus.NoABIInfo)

        distfile_names = bm.get_distfile_names_for_host(host) or []
        if not distfile_names:
            return PackageHostCompat(HostCompatStatus.NoABIInfo)

        unique_names = list(dict.fromkeys(distfile_names))
        reports: list[ABIReport] = []
        sidecars: list[pathlib.Path] = []
        for name in unique_names:
            sidecar = pm.abi_sidecar_for_distfile(name)
            if sidecar is None:
                continue
            report = self._load_sidecar(sidecar)
            if report is None:
                continue
            reports.append(report)
            sidecars.append(sidecar)

        if not reports:
            return PackageHostCompat(HostCompatStatus.NoABIInfo)

        try:
            merged = _merge_reports(reports)
            host_abi = self._prober.probe(merged)
            compat = check_host_compatibility(merged, host_abi)
        except Exception as exc:  # noqa: BLE001 - never break list/install
            self._logger.W(
                _("failed to merge or check ABI sidecars: {err}").format(err=str(exc))
            )
            return PackageHostCompat(
                HostCompatStatus.CompatibilityUnknown,
                sidecars=tuple(sidecars),
            )

        problems = tuple(
            HostCompatProblem(
                check=item.check,
                compatible=item.compatible,
                msgid=item.msgid,
                params=item.params,
            )
            for item in compat.problems()
        )

        if compat.compatible is False:
            status = HostCompatStatus.LikelyIncompatible
        elif compat.compatible is None or len(reports) < len(unique_names):
            status = HostCompatStatus.CompatibilityUnknown
        else:
            status = HostCompatStatus.LikelyCompatible

        return PackageHostCompat(status, problems, tuple(sidecars))

    def _load_sidecar(self, path: pathlib.Path) -> ABIReport | None:
        if path in self._sidecars:
            return self._sidecars[path]

        report: ABIReport | None = None
        try:
            if path.stat().st_size > DEFAULT_MAX_SIDECAR_BYTES:
                raise ValueError(
                    f"sidecar exceeds the {DEFAULT_MAX_SIDECAR_BYTES}-byte limit"
                )
            report = load_abi_report_toml(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001 - sidecars are optional metadata
            self._logger.W(
                _("failed to load ABI sidecar {path}: {err}").format(
                    path=str(path),
                    err=str(exc),
                )
            )
        self._sidecars[path] = report
        return report


def _merge_reports(reports: Sequence[ABIReport]) -> ABIReport:
    records: dict[str, ElfABIRecord] = {}
    errors: list[ABIScanError] = []
    file_count = 0
    excluded_count = 0
    for report in reports:
        for record in report.records:
            records.setdefault(record.sha256, record)
        errors.extend(report.errors)
        file_count += report.summary.file_count
        excluded_count += report.summary.excluded_count

    merged_records = tuple(sorted(records.values(), key=lambda r: r.sha256))
    summary = build_summary(
        merged_records,
        file_count=file_count,
        excluded_count=excluded_count,
    )
    return ABIReport(
        records=merged_records,
        summary=summary,
        errors=tuple(errors),
    )
