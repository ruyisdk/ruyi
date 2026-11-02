from typing import Any

from ruyi.ruyipkg.host_compat import (
    HostCompatProblem,
    HostCompatStatus,
    PackageHostCompat,
    format_problem,
)
from ruyi.ruyipkg.list import _print_pkg_detail
from ruyi.ruyipkg.pkg_manifest import (
    BinaryFileDeclType,
    BoundPackageManifest,
    DistfileDeclType,
    InputPackageManifestType,
)


class _CapturingLogger:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def stdout(self, s: str = "", *, end: str = "\n") -> None:
        self.lines.append(s)


class _FakeRepo:
    repo_id = "test-repo"
    messages: Any = None


def _make_bound_manifest(
    vendor: object,
    *,
    binary: bool = False,
) -> BoundPackageManifest:
    distfiles: list[DistfileDeclType] = (
        [
            {
                "name": "pkg.tar",
                "size": 1,
                "checksums": {"sha256": "0" * 64},
            }
        ]
        if binary
        else []
    )
    data: InputPackageManifestType = {
        "format": "v1",
        "metadata": {
            "desc": "test package",
            "vendor": vendor,  # type: ignore[typeddict-item]
        },
        "distfiles": distfiles,
    }
    if binary:
        binary_decl: list[BinaryFileDeclType] = [
            {"host": "x86_64", "distfiles": ["pkg.tar"]}
        ]
        data["binary"] = binary_decl
    return BoundPackageManifest(
        "toolchain",
        "gcc",
        "1.0.0",
        data,
        _FakeRepo(),  # type: ignore[arg-type]
    )


def _render(vendor: object) -> str:
    logger = _CapturingLogger()
    pm = _make_bound_manifest(vendor)
    _print_pkg_detail(logger, pm, "en_US.UTF-8")  # type: ignore[arg-type]
    return "\n".join(logger.lines)


def test_certified_mark_shown_when_certified() -> None:
    out = _render(
        {"name": "Acme", "eula": None, "data": {"ruyisdk": {"certified": True}}}
    )
    assert "RuyiSDK Certified" in out


def test_certified_mark_absent_when_not_certified() -> None:
    out = _render({"name": "Acme", "eula": None})
    assert "RuyiSDK Certified" not in out


def test_host_compatibility_bullet_and_problems_are_shown() -> None:
    logger = _CapturingLogger()
    pm = _make_bound_manifest({"name": "Acme", "eula": None}, binary=True)
    problem = HostCompatProblem(
        "e-machine",
        False,
        "package targets e_machine(s) {want}, host is {got}",
        {"want": [243], "got": [62]},
    )
    compat = PackageHostCompat(
        HostCompatStatus.LikelyIncompatible,
        problems=(problem,),
    )

    _print_pkg_detail(logger, pm, "en_US.UTF-8", host_compat=compat)  # type: ignore[arg-type]

    out = "\n".join(logger.lines)
    assert HostCompatStatus.LikelyIncompatible.as_rich_markup() in out
    assert format_problem(problem) in out


def test_host_compatibility_unchecked_hint_is_shown() -> None:
    logger = _CapturingLogger()
    pm = _make_bound_manifest({"name": "Acme", "eula": None}, binary=True)
    compat = PackageHostCompat(HostCompatStatus.Unchecked)

    _print_pkg_detail(logger, pm, "en_US.UTF-8", host_compat=compat)  # type: ignore[arg-type]

    assert "--allow-probing-host" in "\n".join(logger.lines)


def test_host_compatibility_hidden_for_non_binary_package() -> None:
    logger = _CapturingLogger()
    pm = _make_bound_manifest({"name": "Acme", "eula": None}, binary=False)
    compat = PackageHostCompat(HostCompatStatus.LikelyIncompatible)

    _print_pkg_detail(logger, pm, "en_US.UTF-8", host_compat=compat)  # type: ignore[arg-type]

    assert HostCompatStatus.LikelyIncompatible.as_rich_markup() not in "\n".join(
        logger.lines
    )
