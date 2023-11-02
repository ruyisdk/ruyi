import glob
import json
import os.path
from typing import Iterable, Tuple, TypedDict

from git import Repo
from rich import print

from .. import log
from .pkg_manifest import PackageManifest
from .profile import ArchProfilesDeclType


class RepoConfigType(TypedDict):
    dist: str


class MetadataRepo:
    def __init__(self, path: str, remote: str, branch: str) -> None:
        self.root = path
        self.remote = remote
        self.branch = branch
        self.repo: Repo | None = None

        self._pkgs: dict[str, dict[str, PackageManifest]] = {}
        self._slug_cache: dict[str, PackageManifest] = {}

    def ensure_git_repo(self) -> Repo:
        if self.repo is not None:
            return self.repo

        if os.path.exists(self.root):
            self.repo = Repo(self.root)
            return self.repo

        log.D(f"{self.root} does not exist, cloning from {self.remote}")

        # TODO: progress bar
        self.repo = Repo.clone_from(self.remote, self.root, branch=self.branch)
        return self.repo

    def sync(self) -> None:
        repo = self.ensure_git_repo()
        remote = repo.remote()
        if remote.url != self.remote:
            log.D(f"updating remote url from {remote.url} to {self.remote}")
            remote.set_url(self.remote, remote.url)
        log.D(f"fetching")
        remote.fetch()
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
        # we can read the config file directly because we're operating from a
        # working tree (as opposed to a bare repo)
        path = os.path.join(self.root, "config.json")
        with open(path, "rb") as fp:
            return json.load(fp)

    def iter_pkg_manifests(self) -> Iterable[PackageManifest]:
        manifests_dir = os.path.join(self.root, "manifests")
        for f in glob.iglob("*/*.json", root_dir=manifests_dir):
            pkg_name, pkg_ver = os.path.split(f)
            pkg_ver = pkg_ver[:-5]  # strip the ".json" suffix
            with open(os.path.join(manifests_dir, f), "rb") as fp:
                yield PackageManifest(pkg_name, pkg_ver, json.load(fp))

    def iter_arch_profiles(self) -> Iterable[ArchProfilesDeclType]:
        profiles_dir = os.path.join(self.root, "profiles")
        for f in glob.iglob("*.json", root_dir=profiles_dir):
            with open(os.path.join(profiles_dir, f), "rb") as fp:
                yield json.load(fp)

    def ensure_pkg_cache(self) -> None:
        if self._pkgs:
            return

        cache: dict[str, dict[str, PackageManifest]] = {}
        slug_cache: dict[str, PackageManifest] = {}
        for pm in self.iter_pkg_manifests():
            if pm.name not in cache:
                cache[pm.name] = {}
            cache[pm.name][pm.ver] = pm

            if pm.slug:
                slug_cache[pm.slug] = pm

        self._pkgs = cache
        self._slug_cache = slug_cache

    def iter_pkgs(self) -> Iterable[Tuple[str, dict[str, PackageManifest]]]:
        if not self._pkgs:
            self.ensure_pkg_cache()

        return self._pkgs.items()

    def get_pkg_by_slug(self, slug: str) -> PackageManifest | None:
        if not self._pkgs:
            self.ensure_pkg_cache()

        return self._slug_cache.get(slug)

    def get_pkg_latest_ver(self, name: str) -> PackageManifest:
        if not self._pkgs:
            self.ensure_pkg_cache()

        all_semvers = [pm.semver for pm in self._pkgs[name].values()]
        latest_ver = max(*all_semvers)
        return self._pkgs[name][str(latest_ver)]
