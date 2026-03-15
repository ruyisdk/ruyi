from typing import Iterable, TYPE_CHECKING

from ..i18n import _
from .entity import EntityStore
from .news_store import NewsItemStore
from .pkg_manifest import BoundPackageManifest, is_prerelease
from .profile import ProfileProxy
from .protocols import ProvidesPackageManifests
from .repo import MetadataRepo, RepoEntry

if TYPE_CHECKING:
    from ..config import GlobalConfig
    from ..telemetry.scope import TelemetryScopeConfig


class CompositeRepo(ProvidesPackageManifests):
    """Aggregates multiple MetadataRepo instances by priority order.

    Packages from higher-priority repos shadow those from lower-priority
    repos when they share the same ``(category, name, version)`` tuple."""

    def __init__(self, entries: list[RepoEntry], gc: "GlobalConfig") -> None:
        # Sort by priority ascending; higher priority repos shadow lower.
        self._entries = sorted(entries, key=lambda e: e.priority)
        self._gc = gc
        self._repos: list[MetadataRepo] | None = None

        # Merged package caches (populated lazily).
        self._merged_categories: dict[
            str, dict[str, dict[str, BoundPackageManifest]]
        ] | None = None
        self._merged_pkgs: dict[str, dict[str, BoundPackageManifest]] | None = None
        self._merged_slugs: dict[str, BoundPackageManifest] | None = None

    def _ensure_repos(self) -> list[MetadataRepo]:
        if self._repos is not None:
            return self._repos
        self._repos = [
            entry.make_metadata_repo(self._gc)
            for entry in self._entries
            if entry.active
        ]
        return self._repos

    def _ensure_merged_cache(self) -> None:
        """Build merged package caches across all repos.

        Iterates repos in ascending priority order so that higher-priority
        entries overwrite lower-priority ones for the same
        ``(category, name, version)`` key."""
        if self._merged_categories is not None:
            return

        categories: dict[str, dict[str, dict[str, BoundPackageManifest]]] = {}
        pkgs_by_name: dict[str, dict[str, BoundPackageManifest]] = {}
        slug_cache: dict[str, BoundPackageManifest] = {}

        # Ascending priority: later repos overwrite earlier for same key.
        for repo in self._ensure_repos():
            for pm in repo.iter_pkg_manifests():
                cat_dict = categories.setdefault(pm.category, {})
                name_dict = cat_dict.setdefault(pm.name, {})
                name_dict[pm.ver] = pm

                by_name = pkgs_by_name.setdefault(pm.name, {})
                by_name[pm.ver] = pm

                if pm.slug:
                    slug_cache[pm.slug] = pm

        self._merged_categories = categories
        self._merged_pkgs = pkgs_by_name
        self._merged_slugs = slug_cache

    def iter_repos(self) -> Iterable[MetadataRepo]:
        """Iterate over all active MetadataRepo instances in priority order
        (ascending)."""
        return iter(self._ensure_repos())

    # --- sync ---

    def sync_all(self) -> None:
        """Sync all active repos."""
        for repo in self._ensure_repos():
            repo.sync()

    # --- ProvidesPackageManifests implementation ---

    def iter_pkg_manifests(self) -> Iterable[BoundPackageManifest]:
        self._ensure_merged_cache()
        assert self._merged_categories is not None
        for cat_pkgs in self._merged_categories.values():
            for ver_dict in cat_pkgs.values():
                yield from ver_dict.values()

    def iter_pkgs(self) -> Iterable[tuple[str, str, dict[str, BoundPackageManifest]]]:
        self._ensure_merged_cache()
        assert self._merged_categories is not None
        for cat, cat_pkgs in self._merged_categories.items():
            for pkg_name, pkg_vers in cat_pkgs.items():
                yield (cat, pkg_name, pkg_vers)

    def get_pkg(
        self,
        name: str,
        category: str,
        ver: str,
    ) -> BoundPackageManifest | None:
        self._ensure_merged_cache()
        assert self._merged_categories is not None
        try:
            return self._merged_categories[category][name][ver]
        except KeyError:
            return None

    def get_pkg_latest_ver(
        self,
        name: str,
        category: str | None = None,
        include_prerelease_vers: bool = False,
    ) -> BoundPackageManifest:
        self._ensure_merged_cache()
        assert self._merged_categories is not None
        assert self._merged_pkgs is not None

        if category is not None:
            pkgset = self._merged_categories[category]
        else:
            pkgset = self._merged_pkgs

        all_semvers = [pm.semver for pm in pkgset[name].values()]
        if not include_prerelease_vers:
            all_semvers = [sv for sv in all_semvers if not is_prerelease(sv)]
        latest_ver = max(all_semvers)
        return pkgset[name][str(latest_ver)]

    def get_pkg_by_slug(self, slug: str) -> BoundPackageManifest | None:
        self._ensure_merged_cache()
        assert self._merged_slugs is not None
        return self._merged_slugs.get(slug)

    def iter_pkg_vers(
        self,
        name: str,
        category: str | None = None,
    ) -> Iterable[BoundPackageManifest]:
        self._ensure_merged_cache()
        assert self._merged_categories is not None
        assert self._merged_pkgs is not None

        if category is not None:
            return self._merged_categories[category][name].values()
        return self._merged_pkgs[name].values()

    # --- Aggregation helpers for MetadataRepo-specific features ---

    @property
    def entity_store(self) -> EntityStore:
        """Combined entity store from all repos.

        Returns the store from the highest-priority repo. Individual repos'
        entity providers are already loaded within each MetadataRepo."""
        repos = self._ensure_repos()
        if not repos:
            return EntityStore(self._gc.logger)
        return repos[-1].entity_store

    def news_store(self) -> NewsItemStore:
        """Aggregated news across all repos.

        News items from all repos are merged by ID. Items with the same ID
        from different repos are combined (each language variant is kept).
        Iteration order is ascending priority so higher-priority repos'
        language files take precedence for same (id, lang) pair."""
        repos = self._ensure_repos()
        if len(repos) <= 1:
            if repos:
                return repos[0].news_store()
            rs_store = self._gc.news_read_status
            rs_store.load()
            merged = NewsItemStore(rs_store)
            merged.finalize()
            return merged

        # Collect all individual news stores, then merge by transferring
        # parsed items. Higher-priority repos overwrite same (id, lang)
        # pairs because we iterate in ascending priority order.
        rs_store = self._gc.news_read_status
        rs_store.load()
        merged = NewsItemStore(rs_store)
        for repo in repos:
            store = repo.news_store()
            for ni in store.list(only_unread=False):
                for nic in ni.langs.values():
                    merged.add_item(ni.id, nic.metadata, nic.post)
        merged.finalize()
        return merged

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
