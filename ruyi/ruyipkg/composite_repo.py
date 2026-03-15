from typing import Iterable, TYPE_CHECKING

from ..i18n import _
from .entity import EntityStore
from .news_store import NewsItemStore
from .pkg_manifest import BoundPackageManifest
from .profile import ProfileProxy
from .protocols import ProvidesPackageManifests
from .repo import MetadataRepo, RepoEntry

if TYPE_CHECKING:
    from ..config import GlobalConfig
    from ..telemetry.scope import TelemetryScopeConfig


class CompositeRepo(ProvidesPackageManifests):
    """Aggregates multiple MetadataRepo instances by priority order.

    In the single-entry case this is a simple passthrough. Multi-entry
    merge logic is added in a later commit."""

    def __init__(self, entries: list[RepoEntry], gc: "GlobalConfig") -> None:
        # Sort by priority ascending; higher priority repos shadow lower.
        self._entries = sorted(entries, key=lambda e: e.priority)
        self._gc = gc
        self._repos: list[MetadataRepo] | None = None

    def _ensure_repos(self) -> list[MetadataRepo]:
        if self._repos is not None:
            return self._repos
        self._repos = [
            entry.make_metadata_repo(self._gc)
            for entry in self._entries
            if entry.active
        ]
        return self._repos

    def iter_repos(self) -> Iterable[MetadataRepo]:
        """Iterate over all active MetadataRepo instances in priority order
        (ascending)."""
        return iter(self._ensure_repos())

    # --- sync ---

    def sync_all(self) -> None:
        """Sync all active repos."""
        for repo in self._ensure_repos():
            repo.sync()

    # --- ProvidesPackageManifests passthrough (single-repo) ---

    def iter_pkg_manifests(self) -> Iterable[BoundPackageManifest]:
        for repo in self._ensure_repos():
            yield from repo.iter_pkg_manifests()

    def iter_pkgs(self) -> Iterable[tuple[str, str, dict[str, BoundPackageManifest]]]:
        for repo in self._ensure_repos():
            yield from repo.iter_pkgs()

    def get_pkg(
        self,
        name: str,
        category: str,
        ver: str,
    ) -> BoundPackageManifest | None:
        # Search in descending priority order (highest priority first)
        for repo in reversed(self._ensure_repos()):
            if result := repo.get_pkg(name, category, ver):
                return result
        return None

    def get_pkg_latest_ver(
        self,
        name: str,
        category: str | None = None,
        include_prerelease_vers: bool = False,
    ) -> BoundPackageManifest:
        # For single-entry, just delegate
        repos = self._ensure_repos()
        if len(repos) == 1:
            return repos[0].get_pkg_latest_ver(
                name, category, include_prerelease_vers
            )
        # Multi-entry: try highest priority first
        for repo in reversed(repos):
            try:
                return repo.get_pkg_latest_ver(
                    name, category, include_prerelease_vers
                )
            except KeyError:
                continue
        raise KeyError(name)

    def get_pkg_by_slug(self, slug: str) -> BoundPackageManifest | None:
        # Search in descending priority order
        for repo in reversed(self._ensure_repos()):
            if result := repo.get_pkg_by_slug(slug):
                return result
        return None

    def iter_pkg_vers(
        self,
        name: str,
        category: str | None = None,
    ) -> Iterable[BoundPackageManifest]:
        # For single-entry, just delegate
        repos = self._ensure_repos()
        if len(repos) == 1:
            return repos[0].iter_pkg_vers(name, category)
        # Multi-entry: chain all repos
        results: list[BoundPackageManifest] = []
        for repo in repos:
            try:
                results.extend(repo.iter_pkg_vers(name, category))
            except KeyError:
                continue
        return results

    # --- Aggregation helpers for MetadataRepo-specific features ---

    @property
    def entity_store(self) -> EntityStore:
        """Combined entity store from all repos."""
        repos = self._ensure_repos()
        if len(repos) == 1:
            return repos[0].entity_store
        # For multi-repo: merge entity stores (later commit)
        return repos[-1].entity_store  # highest priority

    def news_store(self) -> NewsItemStore:
        """Aggregated news across repos."""
        repos = self._ensure_repos()
        if len(repos) == 1:
            return repos[0].news_store()
        # For multi-repo: aggregate (later commit)
        return repos[-1].news_store()  # highest priority

    def get_profile(self, name: str) -> ProfileProxy | None:
        """Priority-ordered profile lookup."""
        for repo in reversed(self._ensure_repos()):
            if p := repo.get_profile(name):
                return p
        return None

    def get_profile_for_arch(self, arch: str, name: str) -> ProfileProxy | None:
        """Priority-ordered profile lookup for a specific arch."""
        for repo in reversed(self._ensure_repos()):
            if p := repo.get_profile_for_arch(arch, name):
                return p
        return None

    def iter_profiles_for_arch(self, arch: str) -> Iterable[ProfileProxy]:
        """Priority-ordered profile iteration for a specific arch."""
        seen: set[str] = set()
        # Descending priority: higher priority profiles shadow lower ones
        for repo in reversed(self._ensure_repos()):
            for p in repo.iter_profiles_for_arch(arch):
                if p.id not in seen:
                    seen.add(p.id)
                    yield p

    def get_supported_arches(self) -> list[str]:
        """Merged set of supported architectures across all repos."""
        arches: set[str] = set()
        for repo in self._ensure_repos():
            arches.update(repo.get_supported_arches())
        return list(arches)

    def run_plugin_cmd(self, cmd_name: str, args: list[str]) -> int:
        """Priority-ordered plugin dispatch."""
        # Try highest priority first
        for repo in reversed(self._ensure_repos()):
            try:
                return repo.run_plugin_cmd(cmd_name, args)
            except RuntimeError:
                continue
        raise RuntimeError(f"command plugin '{cmd_name}' not found in any repo")

    def get_telemetry_api_url(self, scope: "TelemetryScopeConfig") -> str | None:
        """First match wins across repos (highest priority first)."""
        for repo in reversed(self._ensure_repos()):
            if url := repo.get_telemetry_api_url(scope):
                return url
        return None

    def ensure_git_repo(self) -> None:
        """Ensure all active repos have their git repos cloned."""
        for repo in self._ensure_repos():
            repo.ensure_git_repo()

    @property
    def repo_id(self) -> str:
        """Return the repo_id of the highest-priority repo."""
        repos = self._ensure_repos()
        return repos[-1].repo_id if repos else "ruyisdk"

    @property
    def messages(self) -> "RepoMessageStore":
        """Return messages from the highest-priority repo."""
        from .msg import RepoMessageStore

        repos = self._ensure_repos()
        if repos:
            return repos[-1].messages
        return RepoMessageStore.from_object({})
