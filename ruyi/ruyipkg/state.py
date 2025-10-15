import datetime
import json
import os
import pathlib
from typing import Any, Iterable, Iterator, TypedDict, TYPE_CHECKING
from dataclasses import dataclass

from .pkg_manifest import BoundPackageManifest
from .protocols import ProvidesPackageManifests

if TYPE_CHECKING:
    # for avoiding heavy import
    from .repo import MetadataRepo


class PackageInstallationRecord(TypedDict):
    """Record of a package installation."""

    repo_id: str
    category: str
    name: str
    version: str
    host: str  # For binary packages, empty for blobs
    install_path: str
    install_time: str  # ISO format datetime


@dataclass
class PackageInstallationInfo:
    """Information about an installed package."""

    repo_id: str
    category: str
    name: str
    version: str
    host: str  # For binary packages, empty for blobs
    install_path: str
    install_time: datetime.datetime

    def to_record(self) -> PackageInstallationRecord:
        """Convert to a record for JSON serialization."""
        return PackageInstallationRecord(
            repo_id=self.repo_id,
            category=self.category,
            name=self.name,
            version=self.version,
            host=self.host,
            install_path=self.install_path,
            install_time=self.install_time.isoformat(),
        )

    @classmethod
    def from_record(
        cls,
        record: PackageInstallationRecord,
    ) -> "PackageInstallationInfo":
        """Create from a record."""
        return cls(
            repo_id=record["repo_id"],
            category=record["category"],
            name=record["name"],
            version=record["version"],
            host=record["host"],
            install_path=record["install_path"],
            install_time=datetime.datetime.fromisoformat(record["install_time"]),
        )


class RuyipkgGlobalStateStore:
    def __init__(self, root: os.PathLike[Any]) -> None:
        self.root = pathlib.Path(root)
        self._installs_file = self.root / "installs.json"
        self._installs_cache: dict[str, PackageInstallationInfo] | None = None

    def ensure_state_dir(self) -> None:
        """Ensure the state directory exists."""
        self.root.mkdir(parents=True, exist_ok=True)

    def purge_installation_info(self) -> None:
        """Purge installation records."""
        self._installs_file.unlink(missing_ok=True)
        self._installs_cache = None
        # if the state dir is empty, remove it
        try:
            self.root.rmdir()
        except OSError:
            pass

    def _load_installs(self) -> dict[str, PackageInstallationInfo]:
        """Load installation records from disk."""
        if self._installs_cache is not None:
            return self._installs_cache

        self.ensure_state_dir()

        if not self._installs_file.exists():
            self._installs_cache = {}
            return self._installs_cache

        try:
            with open(self._installs_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            installs = {}
            for key, record in data.items():
                installs[key] = PackageInstallationInfo.from_record(record)

            self._installs_cache = installs
            return self._installs_cache
        except (json.JSONDecodeError, KeyError, ValueError):
            # If file is corrupted, start fresh
            self._installs_cache = {}
            return self._installs_cache

    def _save_installs(self) -> None:
        """Save installation records to disk."""
        if self._installs_cache is None:
            return

        self.ensure_state_dir()

        data = {}
        for key, info in self._installs_cache.items():
            data[key] = info.to_record()

        # Write atomically by writing to temp file then renaming
        temp_file = self._installs_file.with_suffix(".tmp")
        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            temp_file.replace(self._installs_file)
        except Exception:
            # Clean up temp file if something went wrong
            if temp_file.exists():
                temp_file.unlink()
            raise

    def _get_installation_key(
        self,
        repo_id: str,
        category: str,
        name: str,
        version: str,
        host: str = "",
    ) -> str:
        """Get the key used to store installation info."""
        if host:
            # Use a format that includes host for binary packages
            return f"{repo_id}:{category}/{name} {version} host={host}"
        return f"{repo_id}:{category}/{name} {version}"

    def record_installation(
        self,
        repo_id: str,
        category: str,
        name: str,
        version: str,
        host: str,
        install_path: str,
    ) -> None:
        """Record a successful package installation."""
        installs = self._load_installs()

        key = self._get_installation_key(repo_id, category, name, version, host)
        info = PackageInstallationInfo(
            repo_id=repo_id,
            category=category,
            name=name,
            version=version,
            host=host,
            install_path=install_path,
            install_time=datetime.datetime.now(),
        )

        installs[key] = info
        self._save_installs()

    def remove_installation(
        self,
        repo_id: str,
        category: str,
        name: str,
        version: str,
        host: str = "",
    ) -> bool:
        """Remove an installation record."""
        installs = self._load_installs()
        key = self._get_installation_key(repo_id, category, name, version, host)

        if key in installs:
            del installs[key]
            self._save_installs()
            return True
        return False

    def get_installation(
        self,
        repo_id: str,
        category: str,
        name: str,
        version: str,
        host: str = "",
    ) -> PackageInstallationInfo | None:
        """Get information about a specific installation."""
        installs = self._load_installs()
        key = self._get_installation_key(repo_id, category, name, version, host)
        return installs.get(key)

    def is_package_installed(
        self,
        repo_id: str,
        category: str,
        name: str,
        version: str,
        host: str = "",
    ) -> bool:
        """Check if a package is installed."""
        return self.get_installation(repo_id, category, name, version, host) is not None

    def list_installed_packages(self) -> list[PackageInstallationInfo]:
        """List all installed packages."""
        installs = self._load_installs()
        return list(installs.values())


class BoundInstallationStateStore(ProvidesPackageManifests):
    def __init__(self, rgs: RuyipkgGlobalStateStore, mr: "MetadataRepo") -> None:
        self._rgs = rgs
        self._mr = mr

    def _get_installed_manifest(
        self,
        info: PackageInstallationInfo,
    ) -> BoundPackageManifest | None:
        """Get the bound manifest for an installed package, or None if not found in repo."""

        return self._mr.get_pkg(info.name, info.category, info.version)

    def iter_pkg_manifests(self) -> Iterable[BoundPackageManifest]:
        """Iterate over all installed package manifests."""

        installed_pkgs = self._rgs.list_installed_packages()
        for info in installed_pkgs:
            if m := self._get_installed_manifest(info):
                yield m

    def iter_pkgs(
        self,
    ) -> Iterable[tuple[str, str, dict[str, BoundPackageManifest]]]:
        """Iterate over installed packages grouped by category and name."""

        installed_pkgs = self._rgs.list_installed_packages()

        # Group by category and name
        result: dict[str, dict[str, dict[str, BoundPackageManifest]]] = {}
        for info in installed_pkgs:
            if m := self._get_installed_manifest(info):
                if info.category not in result:
                    result[info.category] = {}
                if info.name not in result[info.category]:
                    result[info.category][info.name] = {}
                result[info.category][info.name][info.version] = m

        for category, cat_pkgs in result.items():
            for pkg_name, pkg_vers in cat_pkgs.items():
                yield (category, pkg_name, pkg_vers)

    def iter_pkg_vers(
        self,
        name: str,
        category: str | None = None,
    ) -> Iterable[BoundPackageManifest]:
        """Iterate over installed versions of a specific package."""

        installed_pkgs = self._rgs.list_installed_packages()
        for info in installed_pkgs:
            if info.name == name and (category is None or info.category == category):
                if m := self._get_installed_manifest(info):
                    yield m

    def get_pkg(
        self,
        name: str,
        category: str,
        ver: str,
    ) -> BoundPackageManifest | None:
        """Returns the package manifest by exact match, or None if not found."""
        installed_pkgs = self._rgs.list_installed_packages()
        for info in installed_pkgs:
            if info.name == name and info.category == category and info.version == ver:
                if m := self._get_installed_manifest(info):
                    return m
                # Package is installed but not found in current repo
                break

        return None

    def get_pkg_latest_ver(
        self,
        name: str,
        category: str | None = None,
        include_prerelease_vers: bool = False,
    ) -> BoundPackageManifest:
        """Get the latest installed version of a package."""

        from .pkg_manifest import is_prerelease

        installed_vers = list(self.iter_pkg_vers(name, category))
        if not installed_vers:
            raise KeyError(f"No installed versions found for package '{name}'")

        if not include_prerelease_vers:
            installed_vers = [
                pm for pm in installed_vers if not is_prerelease(pm.semver)
            ]
            if not installed_vers:
                raise KeyError(
                    f"No non-prerelease installed versions found for package '{name}'"
                )

        # Find the latest version
        latest = max(installed_vers, key=lambda pm: pm.semver)
        return latest

    # To be removed later along with slug support
    def get_pkg_by_slug(self, slug: str) -> BoundPackageManifest | None:
        """Get an installed package by its slug."""

        installed_pkgs = self._rgs.list_installed_packages()
        for info in installed_pkgs:
            if m := self._get_installed_manifest(info):
                if m.slug == slug:
                    return m
        return None

    # Useful helpers

    def iter_upgradable_pkgs(
        self,
        include_prereleases: bool = False,
    ) -> Iterator[tuple[BoundPackageManifest, str]]:
        for installed_pm in self.iter_pkg_manifests():
            latest_pm: BoundPackageManifest
            try:
                latest_pm = self._mr.get_pkg_latest_ver(
                    installed_pm.name,
                    installed_pm.category,
                    include_prereleases,
                )
            except KeyError:
                # package not found in the repo, skip it
                continue

            if latest_pm.semver > installed_pm.semver:
                yield (installed_pm, str(latest_pm.semver))
