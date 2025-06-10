import datetime
import json
import os
import pathlib
from typing import Any, TypedDict
from dataclasses import dataclass


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
