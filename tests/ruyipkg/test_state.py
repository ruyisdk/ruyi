import datetime
from typing import Iterable, TYPE_CHECKING
from unittest.mock import Mock

try:
    from semver.version import Version  # type: ignore[import-untyped,unused-ignore]
except ModuleNotFoundError:
    # semver 2.x
    from semver import VersionInfo as Version  # type: ignore[import-untyped,unused-ignore]

from ruyi.ruyipkg.state import BoundInstallationStateStore, PackageInstallationInfo

if TYPE_CHECKING:
    from ruyi.ruyipkg.pkg_manifest import BoundPackageManifest


def test_bound_installation_state_store_empty() -> None:
    """Test BoundInstallationStateStore with no installed packages."""
    # Create a mock RuyipkgGlobalStateStore that returns no installed packages
    mock_rgs = Mock()
    mock_rgs.list_installed_packages.return_value = []

    # Create a mock MetadataRepo
    mock_mr = Mock()

    # Create the BoundInstallationStateStore
    store = BoundInstallationStateStore(mock_rgs, mock_mr)

    # Test that it returns no packages
    assert not list(store.iter_pkg_manifests())
    assert not list(store.iter_pkgs())
    assert not list(store.iter_pkg_vers("nonexistent"))
    assert store.get_pkg_by_slug("nonexistent") is None


def test_bound_installation_state_store_with_installed_packages() -> None:
    """Test BoundInstallationStateStore with some installed packages."""
    # Create mock installed packages
    install_info1 = PackageInstallationInfo(
        repo_id="test-repo",
        category="toolchain",
        name="gcc",
        version="13.1.0",
        host="x86_64-linux-gnu",
        install_path="/test/path1",
        install_time=datetime.datetime.now(),
    )

    install_info2 = PackageInstallationInfo(
        repo_id="test-repo",
        category="toolchain",
        name="gcc",
        version="13.2.0",
        host="x86_64-linux-gnu",
        install_path="/test/path2",
        install_time=datetime.datetime.now(),
    )

    # Create mock manifests
    mock_manifest1 = Mock()
    mock_manifest1.category = "toolchain"
    mock_manifest1.name = "gcc"
    mock_manifest1.ver = "13.1.0"
    mock_manifest1.slug = "gcc-13-1-0"
    mock_manifest1.semver = Version.parse("13.1.0")

    mock_manifest2 = Mock()
    mock_manifest2.category = "toolchain"
    mock_manifest2.name = "gcc"
    mock_manifest2.ver = "13.2.0"
    mock_manifest2.slug = "gcc-13-2-0"
    mock_manifest2.semver = Version.parse("13.2.0")

    # Create a mock RuyipkgGlobalStateStore
    mock_rgs = Mock()
    mock_rgs.list_installed_packages.return_value = [install_info1, install_info2]

    # Create a mock MetadataRepo
    mock_mr = Mock()

    def mock_iter_pkg_vers(
        name: str, category: str | None = None
    ) -> "Iterable[BoundPackageManifest]":
        if name == "gcc" and category == "toolchain":
            return [mock_manifest1, mock_manifest2]
        return []

    mock_mr.iter_pkg_vers.side_effect = mock_iter_pkg_vers

    # Create the BoundInstallationStateStore
    store = BoundInstallationStateStore(mock_rgs, mock_mr)

    # Test iter_pkg_manifests
    manifests = list(store.iter_pkg_manifests())
    assert len(manifests) == 2
    assert mock_manifest1 in manifests
    assert mock_manifest2 in manifests

    # Test iter_pkgs
    pkgs = list(store.iter_pkgs())
    assert len(pkgs) == 1
    category, name, versions = pkgs[0]
    assert category == "toolchain"
    assert name == "gcc"
    assert len(versions) == 2
    assert "13.1.0" in versions
    assert "13.2.0" in versions

    # Test iter_pkg_vers
    pkg_versions = list(store.iter_pkg_vers("gcc", "toolchain"))
    assert len(pkg_versions) == 2
    assert mock_manifest1 in pkg_versions
    assert mock_manifest2 in pkg_versions

    # Test get_pkg_latest_ver
    latest = store.get_pkg_latest_ver("gcc", "toolchain")
    # Should return the one with the higher version
    assert latest == mock_manifest2

    # Test get_pkg_by_slug
    result = store.get_pkg_by_slug("gcc-13-1-0")
    assert result == mock_manifest1
