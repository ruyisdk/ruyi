import os.path
import pathlib
import tomllib
from typing import Any, Self, TypedDict

from xdg import BaseDirectory


DEFAULT_REPO_URL = "https://mirror.iscas.ac.cn/git/ruyisdk/packages-index.git"
DEFAULT_REPO_BRANCH = "main"

ENV_VENV_ROOT_KEY = "RUYI_VENV"


class GlobalConfig:
    resource_name = "ruyi"

    def __init__(self) -> None:
        # all defaults
        self.override_repo_dir: str | None = None
        self.override_repo_url: str | None = None
        self.override_repo_branch: str | None = None

    def get_repo_dir(self) -> str:
        return self.override_repo_dir or os.path.join(
            self.ensure_cache_dir(), "packages-index"
        )

    def get_repo_url(self) -> str:
        return self.override_repo_url or DEFAULT_REPO_URL

    def get_repo_branch(self) -> str:
        return self.override_repo_branch or DEFAULT_REPO_BRANCH

    def ensure_distfiles_dir(self) -> str:
        path = pathlib.Path(self.ensure_cache_dir()) / "distfiles"
        path.mkdir(parents=True, exist_ok=True)
        return str(path)

    def get_toolchain_install_root(self, host: str, slug: str) -> str:
        path = pathlib.Path(self.ensure_cache_dir()) / "toolchains" / host / slug
        return str(path)

    @classmethod
    def init_from_config_data(cls, data: dict[str, Any]) -> Self:
        obj = cls()
        # TODO: read from data and override defaults
        return obj

    @classmethod
    def ensure_data_dir(cls) -> str:
        return BaseDirectory.save_data_path(cls.resource_name)

    @classmethod
    def get_first_data_dir(cls) -> str | None:
        for p in BaseDirectory.load_data_paths(cls.resource_name):
            return p

    @classmethod
    def ensure_config_dir(cls) -> str:
        return BaseDirectory.save_config_path(cls.resource_name)

    @classmethod
    def ensure_cache_dir(cls) -> str:
        return BaseDirectory.save_cache_path(cls.resource_name)

    @classmethod
    def get_config_file(cls) -> str | None:
        # TODO: maybe allow customization of config root
        config_dir = BaseDirectory.load_first_config(cls.resource_name)
        if config_dir is None:
            return None
        return os.path.join(config_dir, "config.toml")

    @classmethod
    def load_from_config(cls) -> Self:
        config_path = cls.get_config_file()
        if config_path is None:
            return cls()

        with open(config_path, "rb") as fp:
            return cls.init_from_config_data(tomllib.load(fp))


class VenvConfigType(TypedDict):
    profile: str


class VenvConfigRootType(TypedDict):
    config: VenvConfigType


class VenvCacheType(TypedDict):
    toolchain_bindir: str
    profile_common_flags: str


class VenvCacheRootType(TypedDict):
    cached: VenvCacheType


class RuyiVenvConfig:
    def __init__(self, cfg: VenvConfigRootType, cache: VenvCacheRootType) -> None:
        self.profile = cfg["config"]["profile"]
        self.toolchain_bindir = cache["cached"]["toolchain_bindir"]
        self.profile_common_flags = cache["cached"]["profile_common_flags"]

    @classmethod
    def inside_ruyi_venv(cls) -> bool:
        return ENV_VENV_ROOT_KEY in os.environ

    @classmethod
    def venv_root(cls) -> pathlib.Path:
        return pathlib.Path(os.environ[ENV_VENV_ROOT_KEY])

    @classmethod
    def load_from_venv(cls) -> Self | None:
        if not cls.inside_ruyi_venv():
            return None

        venv_config_path = cls.venv_root() / "config.toml"
        with open(venv_config_path, "rb") as fp:
            cfg: Any = tomllib.load(fp)  # in order to cast to our stricter type

        venv_cache_path = cls.venv_root() / "cached.toml"
        with open(venv_cache_path, "rb") as fp:
            cache: Any = tomllib.load(fp)  # in order to cast to our stricter type

        return cls(cfg, cache)
