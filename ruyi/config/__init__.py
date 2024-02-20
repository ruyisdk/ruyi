import os.path
from os import PathLike
import pathlib
import tomllib
from typing import Any, Iterable, NotRequired, Self, TypedDict

from xdg import BaseDirectory

from .. import log, argv0
from .news import NewsReadStatusStore


DEFAULT_REPO_URL = "https://github.com/ruyisdk/packages-index.git"
DEFAULT_REPO_BRANCH = "main"

ENV_VENV_ROOT_KEY = "RUYI_VENV"


class GlobalConfigPackagesType(TypedDict):
    prereleases: NotRequired[bool]


class GlobalConfigRepoType(TypedDict):
    local: NotRequired[str]
    remote: NotRequired[str]
    branch: NotRequired[str]


class GlobalConfigRootType(TypedDict):
    packages: NotRequired[GlobalConfigPackagesType]
    repo: NotRequired[GlobalConfigRepoType]


class GlobalConfig:
    resource_name = "ruyi"

    def __init__(self) -> None:
        # all defaults
        self.override_repo_dir: str | None = None
        self.override_repo_url: str | None = None
        self.override_repo_branch: str | None = None
        self.include_prereleases = False

        self._news_read_status_store: NewsReadStatusStore | None = None

    def apply_config(self, config_data: GlobalConfigRootType) -> None:
        if pkgs_cfg := config_data.get("packages"):
            self.include_prereleases = pkgs_cfg.get("prereleases", False)

        if section := config_data.get("repo"):
            self.override_repo_dir = section.get("local", None)
            self.override_repo_url = section.get("remote", None)
            self.override_repo_branch = section.get("branch", None)

            if self.override_repo_dir:
                if not pathlib.Path(self.override_repo_dir).is_absolute():
                    log.W(
                        f"the local repo path '{self.override_repo_dir}' is not absolute; ignoring"
                    )
                    self.override_repo_dir = None

    @property
    def cache_root(self) -> str:
        return os.path.join(BaseDirectory.xdg_cache_home, self.resource_name)

    @property
    def data_root(self) -> str:
        return os.path.join(BaseDirectory.xdg_data_home, self.resource_name)

    @property
    def state_root(self) -> str:
        return os.path.join(BaseDirectory.xdg_state_home, self.resource_name)

    @property
    def news_read_status(self) -> NewsReadStatusStore:
        if self._news_read_status_store is not None:
            return self._news_read_status_store

        filename = os.path.join(self.ensure_state_dir(), "news.read.txt")
        self._news_read_status_store = NewsReadStatusStore(filename)
        return self._news_read_status_store

    def get_repo_dir(self) -> str:
        return self.override_repo_dir or os.path.join(self.cache_root, "packages-index")

    def get_repo_url(self) -> str:
        return self.override_repo_url or DEFAULT_REPO_URL

    def get_repo_branch(self) -> str:
        return self.override_repo_branch or DEFAULT_REPO_BRANCH

    def ensure_distfiles_dir(self) -> str:
        path = pathlib.Path(self.ensure_cache_dir()) / "distfiles"
        path.mkdir(parents=True, exist_ok=True)
        return str(path)

    def global_binary_install_root(self, host: str, slug: str) -> str:
        path = pathlib.Path(self.ensure_data_dir()) / "binaries" / host / slug
        return str(path)

    def global_blob_install_root(self, slug: str) -> str:
        path = pathlib.Path(self.ensure_data_dir()) / "blobs" / slug
        return str(path)

    def lookup_binary_install_dir(self, host: str, slug: str) -> PathLike[Any] | None:
        for data_dir in BaseDirectory.load_data_paths(self.resource_name):
            p = pathlib.Path(data_dir) / "binaries" / host / slug
            if p.exists():
                return p
        return None

    @classmethod
    def ensure_data_dir(cls) -> str:
        return BaseDirectory.save_data_path(cls.resource_name)

    @classmethod
    def ensure_config_dir(cls) -> str:
        return BaseDirectory.save_config_path(cls.resource_name)

    @classmethod
    def ensure_cache_dir(cls) -> str:
        return BaseDirectory.save_cache_path(cls.resource_name)

    @classmethod
    def ensure_state_dir(cls) -> str:
        return BaseDirectory.save_state_path(cls.resource_name)

    @classmethod
    def get_config_file(cls) -> str | None:
        # TODO: maybe allow customization of config root
        config_dir = BaseDirectory.load_first_config(cls.resource_name)
        if config_dir is None:
            return None
        return os.path.join(config_dir, "config.toml")

    @classmethod
    def iter_xdg_configs(cls) -> Iterable[os.PathLike[Any]]:
        """
        Yields possible Ruyi config files in all XDG config paths, sorted by precedence
        from lowest to highest (so that each file may be simply applied consecutively).
        """

        all_config_dirs = list(BaseDirectory.load_config_paths(cls.resource_name))
        for config_dir in reversed(all_config_dirs):
            yield pathlib.Path(config_dir) / "config.toml"

    @classmethod
    def load_from_config(cls) -> Self:
        obj = cls()

        for config_path in cls.iter_xdg_configs():
            log.D(f"trying config file: {config_path}")
            try:
                with open(config_path, "rb") as fp:
                    data: Any = tomllib.load(fp)
            except FileNotFoundError:
                continue

            log.D(f"applying config: {data}")
            obj.apply_config(data)

        return obj


class VenvConfigType(TypedDict):
    profile: str
    sysroot: NotRequired[str]


class VenvConfigRootType(TypedDict):
    config: VenvConfigType


class VenvCacheType(TypedDict):
    target_tuple: str
    toolchain_bindir: str
    gcc_install_dir: NotRequired[str]
    profile_common_flags: str
    qemu_bin: NotRequired[str]
    profile_emu_env: NotRequired[dict[str, str]]


class VenvCacheRootType(TypedDict):
    cached: VenvCacheType


class RuyiVenvConfig:
    def __init__(self, cfg: VenvConfigRootType, cache: VenvCacheRootType) -> None:
        self.profile = cfg["config"]["profile"]
        self.sysroot = cfg["config"].get("sysroot")
        self.target_tuple = cache["cached"]["target_tuple"]
        self.toolchain_bindir = cache["cached"]["toolchain_bindir"]
        self.gcc_install_dir = cache["cached"].get("gcc_install_dir")
        self.profile_common_flags = cache["cached"]["profile_common_flags"]
        self.qemu_bin = cache["cached"].get("qemu_bin")
        self.profile_emu_env = cache["cached"].get("profile_emu_env")

    @classmethod
    def explicit_ruyi_venv_root(cls) -> str | None:
        return os.environ.get(ENV_VENV_ROOT_KEY)

    @classmethod
    def venv_root(cls) -> pathlib.Path | None:
        if explicit_root := cls.explicit_ruyi_venv_root():
            return pathlib.Path(explicit_root)

        # check ../.. from argv[0]
        # this only works if it contains a path separator, otherwise it's really
        # hard without an explicit root (/proc/*/exe points to the resolved file,
        # but we want the path to the first symlink without any symlink dereference)
        argv0_path = argv0()
        if os.path.sep not in argv0_path:
            return None

        implied_root = pathlib.Path(os.path.dirname(os.path.dirname(argv0_path)))
        if (implied_root / "ruyi-venv.toml").exists():
            return implied_root

        return None

    @classmethod
    def load_from_venv(cls) -> Self | None:
        venv_root = cls.venv_root()
        if venv_root is None:
            return None

        if cls.explicit_ruyi_venv_root() is not None:
            log.D(f"using explicit venv root {venv_root}")
        else:
            log.D(f"detected implicit venv root {venv_root}")

        venv_config_path = venv_root / "ruyi-venv.toml"
        with open(venv_config_path, "rb") as fp:
            cfg: Any = tomllib.load(fp)  # in order to cast to our stricter type

        venv_cache_path = venv_root / "ruyi-cache.toml"
        with open(venv_cache_path, "rb") as fp:
            cache: Any = tomllib.load(fp)  # in order to cast to our stricter type

        return cls(cfg, cache)
