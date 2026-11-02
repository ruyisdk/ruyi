from typing import Any

from ruyi.ruyipkg.augmented_pkg import AugmentedPkg, AugmentedPkgManifest
from ruyi.ruyipkg.host_compat import HostCompatStatus, PackageHostCompat
from ruyi.ruyipkg.list import _do_list_non_verbose
from ruyi.ruyipkg.pkg_manifest import (
    BoundPackageManifest,
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


def _make_pm() -> BoundPackageManifest:
    data: InputPackageManifestType = {
        "format": "v1",
        "metadata": {
            "desc": "test package",
            "vendor": {"name": "Acme", "eula": None},
        },
        "distfiles": [],
    }
    return BoundPackageManifest(
        "dev-tools",
        "sample-cli",
        "1.0.0",
        data,
        _FakeRepo(),  # type: ignore[arg-type]
    )


def _make_pkg(compat: PackageHostCompat) -> AugmentedPkg:
    pkg = AugmentedPkg()
    pkg.add_version(
        AugmentedPkgManifest(
            _make_pm(),
            [],
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


def test_porcelain_always_contains_host_compat() -> None:
    pkg = _make_pkg(PackageHostCompat(HostCompatStatus.Unchecked))

    version = pkg.to_porcelain()["vers"][0]
    expected: dict[str, Any] = {"status": "unchecked", "problems": []}
    assert version["host_compat"] == expected
