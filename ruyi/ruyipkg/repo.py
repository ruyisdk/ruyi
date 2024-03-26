import glob
import json
import os.path
from typing import Iterable, NotRequired, Tuple, TypedDict, TypeGuard, cast

from pygit2 import clone_repository
from pygit2.repository import Repository
import yaml

from .. import log
from ..utils.git import RemoteGitProgressIndicator, pull_ff_or_die
from .news import NewsItem
from .pkg_manifest import is_prerelease, PackageManifest
from .profile import ArchProfilesDeclType, ProfileDecl, parse_profiles
from .provisioner import ProvisionerConfig


class RepoConfigV0Type(TypedDict):
    dist: str
    doc_uri: NotRequired[str]


def validate_repo_config_v0(x: object) -> TypeGuard[RepoConfigV0Type]:
    if not isinstance(x, dict):
        return False
    if "ruyi-repo" in x:
        return False
    if "dist" not in x or not isinstance(x["dist"], str):
        return False
    if "doc_uri" in x and not isinstance(x["doc_uri"], str):
        return False
    return True


class RepoConfig:
    def __init__(self, dist: str, doc_uri: str | None) -> None:
        self.dist = dist
        self.doc_uri = doc_uri

    @classmethod
    def from_object(cls, obj: object) -> "RepoConfig":
        if not isinstance(obj, dict):
            raise ValueError("repo config must be a dict")
        if "ruyi-repo" in obj:
            raise NotImplementedError
        return cls.from_v0(cast(object, obj))

    @classmethod
    def from_v0(cls, obj: object) -> "RepoConfig":
        if not validate_repo_config_v0(obj):
            # TODO: more detail in the error message
            raise RuntimeError("malformed v0 repo config")
        return cls(obj["dist"], obj.get("doc_uri"))


class MetadataRepo:
    def __init__(self, path: str, remote: str, branch: str) -> None:
        self.root = path
        self.remote = remote
        self.branch = branch
        self.repo: Repository | None = None

        self._cfg: RepoConfig | None = None
        self._pkgs: dict[str, dict[str, PackageManifest]] = {}
        self._categories: dict[str, dict[str, dict[str, PackageManifest]]] = {}
        self._slug_cache: dict[str, PackageManifest] = {}
        self._profile_cache: dict[str, ProfileDecl] = {}
        self._news_cache: list[NewsItem] | None = None
        self._provisioner_config_cache: tuple[ProvisionerConfig | None] | None = None

    def ensure_git_repo(self) -> Repository:
        if self.repo is not None:
            return self.repo

        if os.path.exists(self.root):
            self.repo = Repository(self.root)
            return self.repo

        log.D(f"{self.root} does not exist, cloning from {self.remote}")

        with RemoteGitProgressIndicator() as pr:
            self.repo = clone_repository(
                self.remote,
                self.root,
                checkout_branch=self.branch,
                callbacks=pr,
            )

        return self.repo

    def sync(self) -> None:
        repo = self.ensure_git_repo()
        return pull_ff_or_die(repo, "origin", self.remote, self.branch)

    @property
    def config(self) -> RepoConfig:
        if self._cfg is not None:
            return self._cfg

        self.ensure_git_repo()

        # we can read the config file directly because we're operating from a
        # working tree (as opposed to a bare repo)
        path = os.path.join(self.root, "config.json")
        with open(path, "rb") as fp:
            obj = json.load(fp)

        self._cfg = RepoConfig.from_object(obj)
        return self._cfg

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

    def ensure_provisioner_config_cache(self) -> None:
        cfg_dir = os.path.join(self.root, "provisioner")
        parsed_config: ProvisionerConfig | None = None
        for filename in ("config.yml", "config.yaml"):
            try:
                with open(os.path.join(cfg_dir, filename), "r") as fp:
                    parsed_config = yaml.safe_load(fp)
                    break
            except FileNotFoundError:
                continue

        self._provisioner_config_cache = (parsed_config,)

    def get_provisioner_config(self) -> ProvisionerConfig | None:
        if self._provisioner_config_cache is None:
            self.ensure_provisioner_config_cache()
        assert self._provisioner_config_cache is not None
        return self._provisioner_config_cache[0]
