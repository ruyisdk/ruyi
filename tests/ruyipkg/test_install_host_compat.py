from typing import Any

import pytest

from ruyi.ruyipkg.host_compat import (
    HostCompatProblem,
    HostCompatStatus,
    PackageHostCompat,
)
from ruyi.ruyipkg.install import _warn_host_compat


class _CapturingLogger:
    def __init__(self) -> None:
        self.infos: list[str] = []
        self.warnings: list[str] = []

    def I(self, s: str = "", *args: Any, **kwargs: Any) -> None:  # noqa: E743
        self.infos.append(s)

    def W(self, s: str = "", *args: Any, **kwargs: Any) -> None:
        self.warnings.append(s)


class _FakePm:
    name_for_installation = "sample-cli-1.0.0"


def _warn(status: HostCompatStatus, *problems: HostCompatProblem) -> _CapturingLogger:
    logger = _CapturingLogger()
    _warn_host_compat(
        logger,  # type: ignore[arg-type]
        _FakePm(),  # type: ignore[arg-type]
        PackageHostCompat(status, problems=problems),
    )
    return logger


def test_likely_incompatible_warns_with_problems() -> None:
    logger = _warn(
        HostCompatStatus.LikelyIncompatible,
        HostCompatProblem(
            "e-machine",
            False,
            "package targets e_machine(s) {want}, host is {got}",
            {"want": [243], "got": [62]},
        ),
    )

    assert len(logger.warnings) == 1
    assert any("e-machine" in line for line in logger.infos)


@pytest.mark.parametrize(
    "status",
    [
        HostCompatStatus.Unchecked,
        HostCompatStatus.NoABIInfo,
        HostCompatStatus.LikelyCompatible,
        HostCompatStatus.CompatibilityUnknown,
    ],
)
def test_other_statuses_do_not_warn(status: HostCompatStatus) -> None:
    logger = _warn(status)

    assert logger.warnings == []
    assert logger.infos == []
