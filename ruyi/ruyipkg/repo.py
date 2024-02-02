import glob
import json
import os.path
from typing import Any, Iterable, NotRequired, Tuple, TypedDict, TypeGuard

from git import Repo

from .. import log
from ..utils.git_progress import RemoteGitProgressIndicator
from .news import NewsItem
from .pkg_manifest import is_prerelease, PackageManifest
from .profile import ArchProfilesDeclType, ProfileDecl, parse_profiles


class RepoConfigType(TypedDict):
    dist: str
    doc_uri: NotRequired[str]


def is_repo_config(x: Any) -> TypeGuard[RepoConfigType]:
    if not isinstance(x, dict):
        return False
    if "dist" not in x or not isinstance(x["dist"], str):
        return False
    if "doc_uri" in x and not isinstance(x["doc_uri"], str):
        return False
    return True


class MetadataRepo:
    def __init__(self, path: str, remote: str, branch: str) -> None:
        self.root = path
        self.remote = remote
        self.branch = branch
        self.repo: Repo | None = None

        self._pkgs: dict[str, dict[str, PackageManifest]] = {}
        self._categories: dict[str, dict[str, dict[str, PackageManifest]]] = {}
        self._slug_cache: dict[str, PackageManifest] = {}
        self._profile_cache: dict[str, ProfileDecl] = {}
        self._news_cache: list[NewsItem] | None = None

    def ensure_git_repo(self) -> Repo:
        if self.repo is not None:
            return self.repo

        if os.path.exists(self.root):
            self.repo = Repo(self.root)
            return self.repo

        log.D(f"{self.root} does not exist, cloning from {self.remote}")

        with RemoteGitProgressIndicator() as pr:
            self.repo = Repo.clone_from(
                self.remote,
                self.root,
                branch=self.branch,
                progress=pr.update,
            )

        return self.repo

    def sync(self) -> None:
        repo = self.ensure_git_repo()
        remote = repo.remote()
        if remote.url != self.remote:
            log.D(f"updating remote url from {remote.url} to {self.remote}")
            remote.set_url(self.remote, remote.url)
        log.D(f"fetching")
        with RemoteGitProgressIndicator() as pr:
            remote.fetch(progress=pr)
        # cosmetic touch-up: sync the local head reference to the remote HEAD too
        main_branch = repo.heads[self.branch]
        tgt_commit = remote.refs[self.branch].commit
        log.D(
            f"updating branch {self.branch} head {main_branch} to commit {tgt_commit}"
        )
        main_branch.commit = tgt_commit
        log.D("checking out")
        main_branch.checkout(force=True)

    def get_config(self) -> RepoConfigType:
        self.ensure_git_repo()

        # we can read the config file directly because we're operating from a
        # working tree (as opposed to a bare repo)
        path = os.path.join(self.root, "config.json")
        with open(path, "rb") as fp:
            obj = json.load(fp)

        if not is_repo_config(obj):
            # TODO: more detail in the error message
            raise RuntimeError("malformed repo config.json")
        return obj

    def iter_pkg_manifests(self) -> Iterable[PackageManifest]:
        self.ensure_git_repo()

        manifests_dir = os.path.join(self.root, "manifests")
        for f in os.scandir(manifests_dir):
            if not f.is_dir():
                continue
            yield from self._iter_pkg_manifests_from_category(f.path)

    def _iter_pkg_manifests_from_category(
        self,
        category_dir: str,
    ) -> Iterable[PackageManifest]:
        self.ensure_git_repo()

        category = os.path.basename(category_dir)
        for f in glob.iglob("*/*.json", root_dir=category_dir):
            pkg_name, pkg_ver = os.path.split(f)
            pkg_ver = pkg_ver[:-5]  # strip the ".json" suffix
            with open(os.path.join(category_dir, f), "rb") as fp:
                yield PackageManifest(category, pkg_name, pkg_ver, json.load(fp))

    def get_profile(self, name: str) -> ProfileDecl | None:
        if not self._profile_cache:
            self.ensure_profile_cache()

        return self._profile_cache.get(name)

    def iter_profiles(self) -> Iterable[ProfileDecl]:
        if not self._profile_cache:
            self.ensure_profile_cache()

        return self._profile_cache.values()

    def ensure_profile_cache(self) -> None:
        if self._profile_cache:
            return

        self.ensure_git_repo()
        profiles_dir = os.path.join(self.root, "profiles")

        cache: dict[str, ProfileDecl] = {}
        for f in glob.iglob("*.json", root_dir=profiles_dir):
            with open(os.path.join(profiles_dir, f), "rb") as fp:
                arch_profiles_decl: ArchProfilesDeclType = json.load(fp)
                for p in parse_profiles(arch_profiles_decl):
                    cache[p.name] = p

        self._profile_cache = cache

    def ensure_pkg_cache(self) -> None:
        if self._pkgs:
            return

        self.ensure_git_repo()

        cache_by_name: dict[str, dict[str, PackageManifest]] = {}
        cache_by_category: dict[str, dict[str, dict[str, PackageManifest]]] = {}
        slug_cache: dict[str, PackageManifest] = {}
        for pm in self.iter_pkg_manifests():
            if pm.name not in cache_by_name:
                cache_by_name[pm.name] = {}
            cache_by_name[pm.name][pm.ver] = pm

            if pm.category not in cache_by_category:
                cache_by_category[pm.category] = {pm.name: {}}
            if pm.name not in cache_by_category[pm.category]:
                cache_by_category[pm.category][pm.name] = {}
            cache_by_category[pm.category][pm.name][pm.ver] = pm

            if pm.slug:
                slug_cache[pm.slug] = pm

        self._pkgs = cache_by_name
        self._categories = cache_by_category
        self._slug_cache = slug_cache

    def iter_pkgs(self) -> Iterable[Tuple[str, str, dict[str, PackageManifest]]]:
        if not self._pkgs:
            self.ensure_pkg_cache()

        for cat, cat_pkgs in self._categories.items():
            for pkg_name, pkg_vers in cat_pkgs.items():
                yield (cat, pkg_name, pkg_vers)

    def get_pkg_by_slug(self, slug: str) -> PackageManifest | None:
        if not self._pkgs:
            self.ensure_pkg_cache()

        return self._slug_cache.get(slug)

    def iter_pkg_vers(
        self,
        name: str,
        category: str | None = None,
    ) -> Iterable[PackageManifest]:
        if not self._pkgs:
            self.ensure_pkg_cache()

        if category is not None:
            return self._categories[category][name].values()
        return self._pkgs[name].values()

    def get_pkg_latest_ver(
        self,
        name: str,
        category: str | None = None,
        include_prerelease_vers: bool = False,
    ) -> PackageManifest:
        if not self._pkgs:
            self.ensure_pkg_cache()

        if category is not None:
            pkgset = self._categories[category]
        else:
            pkgset = self._pkgs

        all_semvers = [pm.semver for pm in pkgset[name].values()]
        if not include_prerelease_vers:
            all_semvers = [sv for sv in all_semvers if not is_prerelease(sv)]
        latest_ver = max(all_semvers)
        return pkgset[name][str(latest_ver)]

    def ensure_news_cache(self) -> None:
        if self._news_cache is not None:
            return

        self.ensure_git_repo()
        news_dir = os.path.join(self.root, "news")

        cache: list[NewsItem] = []
        for f in glob.iglob("*.md", root_dir=news_dir):
            with open(os.path.join(news_dir, f), "r") as fp:
                contents = fp.read()
            ni = NewsItem.new(f, contents)
            if ni is None:
                # malformed file name or content
                continue
            cache.append(ni)

        # sort in intended display order
        cache.sort()

        # mark the news item instances with ordinals
        for i, ni in enumerate(cache):
            ni.ordinal = i + 1

        self._news_cache = cache

    def list_newsitems(self) -> list[NewsItem]:
        if self._news_cache is None:
            self.ensure_news_cache()
        assert self._news_cache is not None
        return self._news_cache
