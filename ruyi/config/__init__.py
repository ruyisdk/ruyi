import locale
import os.path
from os import PathLike
import pathlib
import tomllib
from typing import Any, Iterable, NotRequired, Self, TypedDict

from .. import log, argv0
from ..utils.xdg_basedir import XDGBaseDir
from .news import NewsReadStatusStore

DEFAULT_APP_NAME = "ruyi"
DEFAULT_REPO_URL = "https://github.com/ruyisdk/packages-index.git"
DEFAULT_REPO_BRANCH = "main"

ENV_VENV_ROOT_KEY = "RUYI_VENV"


def get_host_path_fragment_for_binary_install_dir(canonicalized_host: str) -> str:
    # e.g. linux/amd64 -> amd64; "windows/amd64" -> "windows-amd64"
    if canonicalized_host.startswith("linux/"):
        return canonicalized_host[6:]
    return canonicalized_host.replace("/", "-")


def _get_lang_code() -> str:
    lang = locale.getlocale()[0]
    return lang or "en_US"


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
    def __init__(self) -> None:
        # all defaults
        self.override_repo_dir: str | None = None
        self.override_repo_url: str | None = None
        self.override_repo_branch: str | None = None
        self.include_prereleases = False

        self._news_read_status_store: NewsReadStatusStore | None = None

        self._lang_code = _get_lang_code()

        self._dirs = XDGBaseDir(DEFAULT_APP_NAME)

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
    def lang_code(self) -> str:
        return self._lang_code

    @property
    def cache_root(self) -> os.PathLike[Any]:
        return self._dirs.app_cache

    @property
    def data_root(self) -> os.PathLike[Any]:
        return self._dirs.app_data

    @property
    def state_root(self) -> os.PathLike[Any]:
        return self._dirs.app_state

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
        host_path = get_host_path_fragment_for_binary_install_dir(host)
        path = pathlib.Path(self.ensure_data_dir()) / "binaries" / host_path / slug
        return str(path)

    def global_blob_install_root(self, slug: str) -> str:
        path = pathlib.Path(self.ensure_data_dir()) / "blobs" / slug
        return str(path)

    def lookup_binary_install_dir(self, host: str, slug: str) -> PathLike[Any] | None:
        host_path = get_host_path_fragment_for_binary_install_dir(host)
        for data_dir in self._dirs.data_dirs:
            p = data_dir / "binaries" / host_path / slug
            if p.exists():
                return p
        return None

    def ensure_data_dir(self) -> os.PathLike[Any]:
        p = self._dirs.app_data
        p.mkdir(parents=True, exist_ok=True)
        return p

    def ensure_cache_dir(self) -> os.PathLike[Any]:
        p = self._dirs.app_cache
        p.mkdir(parents=True, exist_ok=True)
        return p

    def ensure_config_dir(self) -> os.PathLike[Any]:
        p = self._dirs.app_config
        p.mkdir(parents=True, exist_ok=True)
        return p

    def ensure_state_dir(self) -> os.PathLike[Any]:
        p = self._dirs.app_state
        p.mkdir(parents=True, exist_ok=True)
        return p

    def iter_xdg_configs(self) -> Iterable[os.PathLike[Any]]:
        """
        Yields possible Ruyi config files in all XDG config paths, sorted by precedence
        from lowest to highest (so that each file may be simply applied consecutively).
        """

        for config_dir in reversed(list(self._dirs.app_config_dirs)):
            yield config_dir / "config.toml"

    @classmethod
    def load_from_config(cls) -> Self:
        obj = cls()

        for config_path in obj.iter_xdg_configs():
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
