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
