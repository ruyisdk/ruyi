from typing import Any

from ruyi.ruyipkg.augmented_pkg import AugmentedPkg, AugmentedPkgManifest, PkgRemark
from ruyi.ruyipkg.host_compat import HostCompatStatus, PackageHostCompat
from ruyi.ruyipkg.list import _do_list_non_verbose
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


def _make_pm(*, binary: bool = True) -> BoundPackageManifest:
    distfiles: list[DistfileDeclType] = (
        [
            {
                "name": "sample-cli.tar.zst",
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
            "vendor": {"name": "Acme", "eula": None},
        },
        "distfiles": distfiles,
    }
    if binary:
        binary_decl: list[BinaryFileDeclType] = [
            {"host": "x86_64", "distfiles": ["sample-cli.tar.zst"]}
        ]
        data["binary"] = binary_decl
    return BoundPackageManifest(
        "dev-tools",
        "sample-cli",
        "1.0.0",
        data,
        _FakeRepo(),  # type: ignore[arg-type]
    )


def _make_pkg(
    compat: PackageHostCompat,
    *,
    remarks: list[PkgRemark] | None = None,
    binary: bool = True,
) -> AugmentedPkg:
    pkg = AugmentedPkg()
    pkg.add_version(
        AugmentedPkgManifest(
            _make_pm(binary=binary),
            remarks or [],
            None,
            None,
            host_compat=compat,
        )
    )
    return pkg


def test_status_is_hidden_without_the_flag() -> None:
    logger = _CapturingLogger()
    pkg = _make_pkg(PackageHostCompat(HostCompatStatus.LikelyIncompatible))

    _do_list_non_verbose(logger, [pkg], show_host_compat=False)  # type: ignore[arg-type]

    assert HostCompatStatus.LikelyIncompatible.as_rich_markup() not in "\n".join(
        logger.lines
    )


def test_status_is_shown_with_the_flag() -> None:
    logger = _CapturingLogger()
    pkg = _make_pkg(PackageHostCompat(HostCompatStatus.LikelyIncompatible))

    _do_list_non_verbose(logger, [pkg], show_host_compat=True)  # type: ignore[arg-type]

    assert HostCompatStatus.LikelyIncompatible.as_rich_markup() in "\n".join(
        logger.lines
    )


def test_status_is_combined_with_existing_remarks() -> None:
    logger = _CapturingLogger()
    pkg = _make_pkg(
        PackageHostCompat(HostCompatStatus.LikelyCompatible),
        remarks=[PkgRemark.Latest],
    )

    _do_list_non_verbose(logger, [pkg], show_host_compat=True)  # type: ignore[arg-type]

    expected = f"(latest, {HostCompatStatus.LikelyCompatible.as_rich_markup()})"
    assert expected in "\n".join(logger.lines)


def test_status_is_hidden_for_non_binary_packages() -> None:
    logger = _CapturingLogger()
    pkg = _make_pkg(
        PackageHostCompat(HostCompatStatus.LikelyIncompatible),
        binary=False,
    )

    _do_list_non_verbose(logger, [pkg], show_host_compat=True)  # type: ignore[arg-type]

    assert HostCompatStatus.LikelyIncompatible.as_rich_markup() not in "\n".join(
        logger.lines
    )


def test_no_abi_info_is_hidden_from_short_output() -> None:
    logger = _CapturingLogger()
    pkg = _make_pkg(PackageHostCompat(HostCompatStatus.NoABIInfo))

    _do_list_non_verbose(logger, [pkg], show_host_compat=True)  # type: ignore[arg-type]

    assert HostCompatStatus.NoABIInfo.as_rich_markup() not in "\n".join(logger.lines)


def test_porcelain_always_contains_host_compat() -> None:
    pkg = _make_pkg(PackageHostCompat(HostCompatStatus.Unchecked))

    version = pkg.to_porcelain()["vers"][0]
    expected: dict[str, Any] = {"status": "unchecked", "problems": []}
    assert version["host_compat"] == expected
