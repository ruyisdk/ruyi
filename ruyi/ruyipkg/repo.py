import glob
import itertools
import os.path
import pathlib
import sys
from typing import (
    Any,
    Final,
    Iterable,
    Mapping,
    Sequence,
    TypedDict,
    TypeGuard,
    TYPE_CHECKING,
    cast,
)
from urllib import parse

from pygit2 import clone_repository
from pygit2.repository import Repository

from ..log import RuyiLogger
from ..pluginhost.ctx import PluginHostContext
from ..telemetry.scope import TelemetryScopeConfig
from ..utils.git import RemoteGitProgressIndicator, pull_ff_or_die
from ..utils.url import urljoin_for_sure
from .entity import EntityStore
from .entity_provider import BaseEntityProvider, FSEntityProvider
from .msg import RepoMessageStore
from .news_store import NewsItemStore
from .pkg_manifest import (
    BoundPackageManifest,
    DistfileDecl,
    InputPackageManifestType,
    is_prerelease,
)
from .profile import PluginProfileProvider, ProfileEntityProvider, ProfileProxy
from .protocols import ProvidesPackageManifests

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

if TYPE_CHECKING:
    from typing_extensions import NotRequired

    # for avoiding circular import
    from ..config import GlobalConfig


class RepoConfigV0Type(TypedDict):
    dist: str
    doc_uri: "NotRequired[str]"


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


class RepoConfigV1Repo(TypedDict):
    doc_uri: "NotRequired[str]"


class RepoConfigV1Mirror(TypedDict):
    id: str
    urls: list[str]


class RepoConfigV1Telemetry(TypedDict):
    id: str
    scope: TelemetryScopeConfig
    url: str


RepoConfigV1Type = TypedDict(
    "RepoConfigV1Type",
    {
        "ruyi-repo": str,
        "repo": "NotRequired[RepoConfigV1Repo]",
        "mirrors": list[RepoConfigV1Mirror],
        "telemetry": "NotRequired[list[RepoConfigV1Telemetry]]",
    },
)


def validate_repo_config_v1(x: object) -> TypeGuard[RepoConfigV1Type]:
    if not isinstance(x, dict):
        return False
    x = cast(dict[str, object], x)
    if x.get("ruyi-repo", "") != "v1":
        return False
    return True


MIRROR_ID_RUYI_DIST: Final = "ruyi-dist"


class RepoConfig:
    def __init__(
        self,
        mirrors: list[RepoConfigV1Mirror],
        repo: RepoConfigV1Repo | None,
        telemetry_apis: list[RepoConfigV1Telemetry] | None,
    ) -> None:
        self.mirrors = {x["id"]: x["urls"] for x in mirrors}
        self.repo = repo

        self.telemetry_apis: dict[str, RepoConfigV1Telemetry]
        if telemetry_apis is not None:
            self.telemetry_apis = {x["id"]: x for x in telemetry_apis}
        else:
            self.telemetry_apis = {}

    @classmethod
    def from_object(cls, obj: object) -> "RepoConfig":
        if not isinstance(obj, dict):
            raise ValueError("repo config must be a dict")
        if "ruyi-repo" in obj:
            return cls.from_v1(cast(object, obj))
        return cls.from_v0(cast(object, obj))

    @classmethod
    def from_v0(cls, obj: object) -> "RepoConfig":
        if not validate_repo_config_v0(obj):
            # TODO: more detail in the error message
            raise RuntimeError("malformed v0 repo config")

        v1_mirrors: list[RepoConfigV1Mirror] = [
            {
                "id": MIRROR_ID_RUYI_DIST,
                "urls": [urljoin_for_sure(obj["dist"], "dist/")],
            },
        ]

        v1_repo: RepoConfigV1Repo | None = None
        if "doc_uri" in obj:
            v1_repo = {"doc_uri": obj["doc_uri"]}

        return cls(v1_mirrors, v1_repo, None)

    @classmethod
    def from_v1(cls, obj: object) -> "RepoConfig":
        if not validate_repo_config_v1(obj):
            # TODO: more detail in the error message
            raise RuntimeError("malformed v1 repo config")
        return cls(obj["mirrors"], obj.get("repo"), obj.get("telemetry"))

    def get_dist_urls_for_file(self, logger: RuyiLogger, url: str) -> list[str]:
        u = parse.urlparse(url)
        path = u.path.lstrip("/")
        match u.scheme:
            case "":
                return self.get_mirror_urls_for_file(MIRROR_ID_RUYI_DIST, path)
            case "mirror":
                return self.get_mirror_urls_for_file(u.netloc, path)
            case "http" | "https":
                # pass-through known protocols
                return [url]
            case _:
                # deny others
                logger.W(f"unrecognized dist URL scheme: {u.scheme}")
                return []

    def get_mirror_urls_for_file(self, mirror_id: str, path: str) -> list[str]:
        mirror_urls = self.mirrors.get(mirror_id, [])
        return [parse.urljoin(base, path) for base in mirror_urls]

    def get_telemetry_api_url(self, scope: TelemetryScopeConfig) -> str | None:
        for api_decl in self.telemetry_apis.values():
            if api_decl.get("scope", "") == scope:
                return api_decl.get("url", None)
        return None


class ArchProfileStore:
    def __init__(self, phctx: PluginHostContext[Any, Any], arch: str) -> None:
        self._arch = arch
        plugin_id = f"ruyi-profile-{arch}"
        self._provider = PluginProfileProvider(phctx, plugin_id)
        self._init_cache()

    def _init_cache(self) -> None:
        self._profiles_cache: dict[str, ProfileProxy] = {}
        for profile_id in self._provider.list_all_profile_ids():
            self._profiles_cache[profile_id] = ProfileProxy(
                self._provider, self._arch, profile_id
            )

    def __contains__(self, profile_id: str) -> bool:
        return profile_id in self._profiles_cache

    def __getitem__(self, profile_id: str) -> ProfileProxy:
        try:
            return self._profiles_cache[profile_id]
        except KeyError as e:
            raise KeyError(
                f"profile '{profile_id}' is not supported by this arch"
            ) from e

    def get(self, profile_id: str) -> ProfileProxy | None:
        return self._profiles_cache.get(profile_id)

    def iter_profiles(self) -> Iterable[ProfileProxy]:
        return self._profiles_cache.values()


class MetadataRepo(ProvidesPackageManifests):
    def __init__(self, gc: "GlobalConfig") -> None:
        self._gc = gc
        self.root = gc.get_repo_dir()
        self.remote = gc.get_repo_url()
        self.branch = gc.get_repo_branch()
        self.repo: Repository | None = None

        self._cfg: RepoConfig | None = None
        self._cfg_initialized = False
        self._messages: RepoMessageStore | None = None
        self._pkgs: dict[str, dict[str, BoundPackageManifest]] = {}
        self._categories: dict[str, dict[str, dict[str, BoundPackageManifest]]] = {}
        self._slug_cache: dict[str, BoundPackageManifest] = {}
        self._supported_arches: set[str] | None = None
        self._arch_profile_stores: dict[str, ArchProfileStore] = {}
        self._news_cache: NewsItemStore | None = None
        self._entity_store: EntityStore = EntityStore(
            gc.logger,
            FSEntityProvider(gc.logger, pathlib.Path(self.root) / "entities"),
            MetadataRepoEntityProvider(self),
            ProfileEntityProvider(self),
        )
        self._plugin_host_ctx = PluginHostContext.new(gc.logger, self.plugin_root)
        self._plugin_fn_evaluator = self._plugin_host_ctx.make_evaluator()

    @property
    def repo_id(self) -> str:
        # TODO: proper multi-repo support
        return "ruyisdk"

    @property
    def logger(self) -> RuyiLogger:
        return self._gc.logger

    @property
    def plugin_root(self) -> pathlib.Path:
        return pathlib.Path(self.root) / "plugins"

    def iter_plugin_ids(self) -> Iterable[str]:
        try:
            for p in self.plugin_root.iterdir():
                if p.is_dir():
                    yield p.name
        except (FileNotFoundError, NotADirectoryError):
            pass

    def get_from_plugin(self, plugin_id: str, key: str) -> object | None:
        return self._plugin_host_ctx.get_from_plugin(plugin_id, key)

    def eval_plugin_fn(
        self,
        function: object,
        *args: object,
        **kwargs: object,
    ) -> object:
        """Evaluates a function from a plugin.

        NOTE: There is security implication for the unsandboxed plugin backend,
        which provides **NO GUARDS** against arbitrary inputs for the ``function``
        argument because there is **no sandbox**."""

        return self._plugin_fn_evaluator.eval_function(function, *args, **kwargs)

    def ensure_git_repo(self) -> Repository:
        if self.repo is not None:
            return self.repo

        if os.path.exists(self.root):
            self.repo = Repository(self.root)
            return self.repo

        self.logger.I(
            f"the package repository does not exist at [yellow]{self.root}[/]"
        )
        self.logger.I(f"cloning from [cyan link={self.remote}]{self.remote}[/]")

        with RemoteGitProgressIndicator() as pr:
            repo = clone_repository(
                self.remote,
                self.root,
                checkout_branch=self.branch,
                callbacks=pr,
            )
            # pygit2's type info is incomplete as of 1.16.0, and pyright
            # will not look at the typeshed stub for the appropriate signature
            # because pygit2 has the py.typed marker. Workaround the error for
            # now by explicitly casting to the right runtime type.
            self.repo = cast(Repository, repo)  # type: ignore[redundant-cast]

        # reinit config after cloning
        self._cfg_initialized = False
        self._read_config(False)

        return self.repo

    def sync(self) -> None:
        self._gc.logger.I("updating the package repository")

        repo = self.ensure_git_repo()

        # only manage the repo settings on the user's behalf if the user
        # has not overridden the repo directory themselves
        allow_auto_management = not self._gc.have_overridden_repo_dir

        pull_ff_or_die(
            self.logger,
            repo,
            "origin",
            self.remote,
            self.branch,
            allow_auto_management=allow_auto_management,
        )

        self._gc.logger.I("package repository is updated")

    @property
    def global_config(self) -> "GlobalConfig":
        return self._gc

    @property
    def config(self) -> RepoConfig:
        x = self._read_config(True)
        assert x is not None
        return x

    @property
    def maybe_config(self) -> RepoConfig | None:
        """Like ``config``, but does not pull down the repo in case the repo is
        not locally present at invocation time."""
        return self._read_config(False)

    def _read_config(self, ensure_if_not_existing: bool) -> RepoConfig | None:
        if self._cfg_initialized:
            return self._cfg

        if ensure_if_not_existing:
            self.ensure_git_repo()

        # we can read the config file directly because we're operating from a
        # working tree (as opposed to a bare repo)
        #
        # this is a fake loop (that "loops" only once)
        # here it's only for being able to use break's
        while True:
            try:
                with open(os.path.join(self.root, "config.toml"), "rb") as fp:
                    obj = tomllib.load(fp)
                    break
            except FileNotFoundError:
                pass

            self._cfg_initialized = True
            return None

        self._cfg_initialized = True
        self._cfg = RepoConfig.from_object(obj)
        return self._cfg

    @property
    def messages(self) -> RepoMessageStore:
        if self._messages is not None:
            return self._messages

        self.ensure_git_repo()

        obj: dict[str, object] = {}
        try:
            with open(os.path.join(self.root, "messages.toml"), "rb") as fp:
                obj = tomllib.load(fp)
        except FileNotFoundError:
            pass

        self._messages = RepoMessageStore.from_object(obj)
        return self._messages

    def iter_pkg_manifests(
        self,
        ensure_repo: bool = True,
    ) -> Iterable[BoundPackageManifest]:
        if ensure_repo:
            self.ensure_git_repo()

        manifests_dir = os.path.join(self.root, "manifests")
        try:
            for f in os.scandir(manifests_dir):
                if not f.is_dir():
                    continue
                yield from self._iter_pkg_manifests_from_category(f.path)
        except FileNotFoundError:
            return

    def _iter_pkg_manifests_from_category(
        self,
        category_dir: str,
    ) -> Iterable[BoundPackageManifest]:
        self.ensure_git_repo()

        category = os.path.basename(category_dir)

        # all valid semver strings start with a number
        for f in glob.iglob("*/[0-9]*.toml", root_dir=category_dir):
            pkg_name, pkg_ver = os.path.split(f)
            pkg_ver = pkg_ver[:-5]  # strip the ".toml" suffix
            with open(os.path.join(category_dir, f), "rb") as fp:
                yield BoundPackageManifest(
                    category,
                    pkg_name,
                    pkg_ver,
                    cast(InputPackageManifestType, tomllib.load(fp)),
                    self,
                )

    def get_supported_arches(self) -> list[str]:
        if self._supported_arches is not None:
            return list(self._supported_arches)

        res: set[str] = set()
        for plugin_id in self.iter_plugin_ids():
            if plugin_id.startswith("ruyi-profile-"):
                res.add(plugin_id[13:])
        self._supported_arches = res
        return list(res)

    def get_profile(self, name: str) -> ProfileProxy | None:
        # TODO: deprecate this after making sure every call site has gained
        # arch-awareness
        for arch in self.get_supported_arches():
            store = self.ensure_profile_store_for_arch(arch)
            if p := store.get(name):
                return p
        return None

    def get_profile_for_arch(self, arch: str, name: str) -> ProfileProxy | None:
        store = self.ensure_profile_store_for_arch(arch)
        return store.get(name)

    def iter_profiles_for_arch(self, arch: str) -> Iterable[ProfileProxy]:
        store = self.ensure_profile_store_for_arch(arch)
        return store.iter_profiles()

    def ensure_profile_store_for_arch(self, arch: str) -> ArchProfileStore:
        if arch in self._arch_profile_stores:
            return self._arch_profile_stores[arch]

        self.ensure_git_repo()
        store = ArchProfileStore(self._plugin_host_ctx, arch)
        self._arch_profile_stores[arch] = store
        return store

    def ensure_pkg_cache(
        self,
        ensure_repo: bool = True,
    ) -> None:
        if self._pkgs:
            return

        if ensure_repo:
            self.ensure_git_repo()

        cache_by_name: dict[str, dict[str, BoundPackageManifest]] = {}
        cache_by_category: dict[str, dict[str, dict[str, BoundPackageManifest]]] = {}
        slug_cache: dict[str, BoundPackageManifest] = {}
        for pm in self.iter_pkg_manifests(ensure_repo=ensure_repo):
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

    def iter_pkgs(
        self,
        ensure_repo: bool = True,
    ) -> Iterable[tuple[str, str, dict[str, BoundPackageManifest]]]:
        if not self._pkgs:
            self.ensure_pkg_cache(ensure_repo=ensure_repo)

        for cat, cat_pkgs in self._categories.items():
            for pkg_name, pkg_vers in cat_pkgs.items():
                yield (cat, pkg_name, pkg_vers)

    def get_pkg_by_slug(
        self,
        slug: str,
        ensure_repo: bool = True,
    ) -> BoundPackageManifest | None:
        if not self._pkgs:
            self.ensure_pkg_cache(ensure_repo=ensure_repo)

        return self._slug_cache.get(slug)

    def iter_pkg_vers(
        self,
        name: str,
        category: str | None = None,
        ensure_repo: bool = True,
    ) -> Iterable[BoundPackageManifest]:
        if not self._pkgs:
            self.ensure_pkg_cache(ensure_repo=ensure_repo)

        if category is not None:
            return self._categories[category][name].values()
        return self._pkgs[name].values()

    def get_pkg(
        self,
        name: str,
        category: str,
        ver: str,
        *,
        ensure_repo: bool = True,
    ) -> BoundPackageManifest | None:
        if not self._pkgs:
            self.ensure_pkg_cache(ensure_repo=ensure_repo)

        try:
            return self._categories[category][name][ver]
        except KeyError:
            return None

    def get_pkg_latest_ver(
        self,
        name: str,
        category: str | None = None,
        include_prerelease_vers: bool = False,
        ensure_repo: bool = True,
    ) -> BoundPackageManifest:
        if not self._pkgs:
            self.ensure_pkg_cache(ensure_repo=ensure_repo)

        if category is not None:
            pkgset = self._categories[category]
        else:
            pkgset = self._pkgs

        all_semvers = [pm.semver for pm in pkgset[name].values()]
        if not include_prerelease_vers:
            all_semvers = [sv for sv in all_semvers if not is_prerelease(sv)]
        latest_ver = max(all_semvers)
        return pkgset[name][str(latest_ver)]

    def get_distfile_urls(self, decl: DistfileDecl) -> list[str]:
        urls_to_expand: list[str] = []
        if not decl.is_restricted("mirror"):
            urls_to_expand.append(f"mirror://{MIRROR_ID_RUYI_DIST}/{decl.name}")

        if decl.urls:
            urls_to_expand.extend(decl.urls)

        cfg = self.config
        return list(
            itertools.chain(
                *(
                    cfg.get_dist_urls_for_file(self.logger, url)
                    for url in urls_to_expand
                )
            )
        )

    def ensure_news_cache(
        self,
        ensure_repo: bool = True,
    ) -> None:
        if self._news_cache is not None:
            return

        if ensure_repo:
            self.ensure_git_repo()
        news_dir = os.path.join(self.root, "news")

        rs_store = self._gc.news_read_status
        rs_store.load()

        cache = NewsItemStore(rs_store)
        try:
            for f in glob.iglob("*.md", root_dir=news_dir):
                with open(os.path.join(news_dir, f), "r", encoding="utf-8") as fp:
                    try:
                        contents = fp.read()
                    except UnicodeDecodeError:
                        self.logger.W(
                            f"UnicodeDecodeError: {os.path.join(news_dir, f)}"
                        )
                        continue
                    cache.add(f, contents)  # may fail but failures are harmless
        except FileNotFoundError:
            pass

        cache.finalize()
        self._news_cache = cache

    def news_store(
        self,
        ensure_repo: bool = True,
    ) -> NewsItemStore:
        if self._news_cache is None:
            self.ensure_news_cache(ensure_repo=ensure_repo)
        assert self._news_cache is not None
        return self._news_cache

    def run_plugin_cmd(self, cmd_name: str, args: list[str]) -> int:
        plugin_id = f"ruyi-cmd-{cmd_name.lower()}"

        plugin_entrypoint = self._plugin_host_ctx.get_from_plugin(
            plugin_id,
            "plugin_cmd_main_v1",
            is_cmd_plugin=True,  # allow access to host FS for command plugins
        )
        if plugin_entrypoint is None:
            raise RuntimeError(f"cmd entrypoint not found in plugin '{plugin_id}'")

        ret = self.eval_plugin_fn(plugin_entrypoint, args)
        if not isinstance(ret, int):
            self.logger.W(
                f"unexpected return type of cmd plugin '{plugin_id}': {type(ret)} is not int."
            )
            self.logger.I("forcing return code to 1; the plugin should be fixed")
            ret = 1
        return ret

    @property
    def entity_store(self) -> EntityStore:
        """Get the entity store for this repository."""
        return self._entity_store

    def get_telemetry_api_url(self, scope: TelemetryScopeConfig) -> str | None:
        # do not clone the metadata repo if it is absent, in case the user
        # is simply trying trivial commands like `ruyi version`.
        if repo_cfg := self.maybe_config:
            return repo_cfg.get_telemetry_api_url(scope)
        return None


PACKAGE_ENTITY_TYPE = "pkg"
PACKAGE_ENTITY_TYPE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "required": ["pkg"],
    "properties": {
        "pkg": {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "display_name": {"type": "string"},
                "name": {"type": "string"},
                "category": {"type": "string"},
            },
            "required": ["id", "display_name", "name", "category"],
        },
        "related": {
            "type": "array",
            "description": "List of related entity references",
            "items": {"type": "string", "pattern": "^.+:.+"},
        },
        "unique_among_type_during_traversal": {
            "type": "boolean",
            "description": "Whether this entity should be unique among all entities of the same type during traversal",
        },
    },
}


class PackageEntityData(TypedDict):
    id: str
    display_name: str
    name: str
    category: str


class PackageEntity(TypedDict):
    pkg: PackageEntityData
    related: "NotRequired[list[str]]"
    unique_among_type_during_traversal: "NotRequired[bool]"


class MetadataRepoEntityProvider(BaseEntityProvider):
    def __init__(self, repo: MetadataRepo) -> None:
        super().__init__()
        self._repo = repo

    def discover_schemas(self) -> dict[str, object]:
        return {
            PACKAGE_ENTITY_TYPE: PACKAGE_ENTITY_TYPE_SCHEMA,
        }

    def load_entities(
        self,
        entity_types: Sequence[str],
    ) -> Mapping[str, Mapping[str, Mapping[str, Any]]]:
        result: dict[str, Mapping[str, Mapping[str, Any]]] = {}
        for ty in entity_types:
            if ty == PACKAGE_ENTITY_TYPE:
                result[ty] = self._load_package_entities()
        return result

    def _load_package_entities(self) -> dict[str, PackageEntity]:
        result: dict[str, PackageEntity] = {}
        for cat, pkg_name, pkg_vers in self._repo.iter_pkgs():
            full_name = f"{cat}/{pkg_name}"
            relations = []

            # see if all versions of the package are toolchains and share the
            # same arch
            tc_arch: str | None = None
            for pkg_ver in pkg_vers.values():
                if tm := pkg_ver.toolchain_metadata:
                    if tc_arch is None:
                        tc_arch = tm.target_arch
                        continue
                    if tc_arch != tm.target_arch:
                        tc_arch = None
                        break
                else:
                    break
            if tc_arch is not None:
                # this is a toolchain package, add the arch as a related entity
                relations.append(f"arch:{tc_arch}")

            # similarly, check for the emulator kind
            emu_arches: set[str] | None = None
            for pkg_ver in pkg_vers.values():
                if em := pkg_ver.emulator_metadata:
                    pkg_ver_arches: set[str] = set()
                    for p in em.programs:
                        pkg_ver_arches.update(p.supported_arches)
                    if emu_arches is None:
                        emu_arches = pkg_ver_arches
                        continue
                    if emu_arches != pkg_ver_arches:
                        emu_arches = emu_arches.intersection(pkg_ver_arches)
                else:
                    break
            if emu_arches is not None:
                for emu_arch in emu_arches:
                    relations.append(f"arch:{emu_arch}")

            result[full_name] = {
                "pkg": {
                    "id": full_name,
                    "display_name": full_name,
                    "name": pkg_name,
                    "category": cat,
                },
                "related": relations,
            }
        return result
