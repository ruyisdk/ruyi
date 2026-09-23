import datetime
import pathlib
from typing import Iterable, TYPE_CHECKING
from unittest.mock import Mock

try:
    from semver.version import Version  # type: ignore[import-untyped,unused-ignore]
except ModuleNotFoundError:
    # semver 2.x
    from semver import VersionInfo as Version  # type: ignore[import-untyped,unused-ignore]

from ruyi.ruyipkg.state import (
    BoundInstallationStateStore,
    PackageInstallationInfo,
    RuyipkgGlobalStateStore,
)

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

    def mock_get_pkg(
        name: str, category: str, ver: str
    ) -> "BoundPackageManifest | None":
        if name == "gcc" and category == "toolchain":
            if ver == "13.1.0":
                return mock_manifest1
            elif ver == "13.2.0":
                return mock_manifest2
        return None

    def mock_iter_pkg_vers(
        name: str, category: str | None = None
    ) -> "Iterable[BoundPackageManifest]":
        if name == "gcc" and category == "toolchain":
            return [mock_manifest1, mock_manifest2]
        return []

    mock_mr.get_pkg.side_effect = mock_get_pkg
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

    # Test get_pkg method
    pkg = store.get_pkg("gcc", "toolchain", "13.1.0")
    assert pkg == mock_manifest1

    pkg = store.get_pkg("gcc", "toolchain", "13.2.0")
    assert pkg == mock_manifest2

    # Test get_pkg with non-existent package
    result = store.get_pkg("nonexistent", "toolchain", "1.0.0")
    assert result is None

    result = store.get_pkg("gcc", "nonexistent", "13.1.0")
    assert result is None

    result = store.get_pkg("gcc", "toolchain", "99.0.0")
    assert result is None


class TestCrossRepoInstallationState:
    """Regression tests for https://github.com/ruyisdk/ruyi/issues/501.

    Installation locations are shared between repos, so installation
    records must be queryable and removable regardless of the repo they
    were originally recorded under. Otherwise, after switching to a
    different repo carrying the same package version, installed packages
    would forever appear as not installed.
    """

    @staticmethod
    def _record_test_pkg(store: RuyipkgGlobalStateStore, repo_id: str) -> None:
        store.record_installation(
            repo_id=repo_id,
            category="board-image",
            name="uboot-revyos-milkv-meles-8g",
            version="1.0.0",
            host="",
            install_path="/fake/install/root",
        )

    def test_installation_recorded_under_other_repo_is_recognized(
        self,
        tmp_path: pathlib.Path,
    ) -> None:
        store = RuyipkgGlobalStateStore(tmp_path)
        self._record_test_pkg(store, "repo-a")

        # The same package version is now queried in the context of another
        # repo, e.g. after the user switched to a different repo.
        assert store.is_package_installed(
            "repo-b", "board-image", "uboot-revyos-milkv-meles-8g", "1.0.0", ""
        )

        info = store.get_installation(
            "repo-b", "board-image", "uboot-revyos-milkv-meles-8g", "1.0.0", ""
        )
        assert info is not None
        # the original provenance must be preserved
        assert info.repo_id == "repo-a"

    def test_cross_repo_recognition_survives_reload(
        self,
        tmp_path: pathlib.Path,
    ) -> None:
        store = RuyipkgGlobalStateStore(tmp_path)
        self._record_test_pkg(store, "repo-a")

        # Each ruyi invocation reloads the state from disk, so the
        # cross-repo recognition must work with a fresh store instance.
        fresh_store = RuyipkgGlobalStateStore(tmp_path)
        assert fresh_store.is_package_installed(
            "repo-b", "board-image", "uboot-revyos-milkv-meles-8g", "1.0.0", ""
        )

    def test_installation_identity_still_distinct(
        self,
        tmp_path: pathlib.Path,
    ) -> None:
        store = RuyipkgGlobalStateStore(tmp_path)
        self._record_test_pkg(store, "repo-a")

        # Records must not be conflated across distinct installation
        # identities even when queried cross-repo.
        assert not store.is_package_installed(
            "repo-b", "board-image", "uboot-revyos-milkv-meles-8g", "2.0.0", ""
        )
        assert not store.is_package_installed(
            "repo-b", "board-image", "other-pkg", "1.0.0", ""
        )
        assert not store.is_package_installed(
            "repo-b", "other-category", "uboot-revyos-milkv-meles-8g", "1.0.0", ""
        )
        assert not store.is_package_installed(
            "repo-b", "board-image", "uboot-revyos-milkv-meles-8g", "1.0.0", "riscv64"
        )

    def test_remove_installation_recorded_under_other_repo(
        self,
        tmp_path: pathlib.Path,
    ) -> None:
        store = RuyipkgGlobalStateStore(tmp_path)
        self._record_test_pkg(store, "repo-a")

        # Uninstalling while another repo is active must still remove the
        # record, because the files on disk are shared between repos.
        assert store.remove_installation(
            "repo-b", "board-image", "uboot-revyos-milkv-meles-8g", "1.0.0", ""
        )
        assert not store.is_package_installed(
            "repo-a", "board-image", "uboot-revyos-milkv-meles-8g", "1.0.0", ""
        )
        assert store.list_installed_packages() == []

    def test_remove_installation_covers_duplicate_cross_repo_records(
        self,
        tmp_path: pathlib.Path,
    ) -> None:
        store = RuyipkgGlobalStateStore(tmp_path)
        # Such duplicates exist in the wild, e.g. created by a --reinstall
        # after switching repos with older ruyi versions.
        self._record_test_pkg(store, "repo-a")
        self._record_test_pkg(store, "repo-b")

        assert store.remove_installation(
            "repo-b", "board-image", "uboot-revyos-milkv-meles-8g", "1.0.0", ""
        )
        assert store.list_installed_packages() == []
