import datetime
from functools import cached_property
import locale
import os.path
from os import PathLike
import pathlib
import sys
from typing import Any, Final, Iterable, Sequence, TypedDict, TYPE_CHECKING

if TYPE_CHECKING:
    from typing_extensions import NotRequired, Self

    from ..log import RuyiLogger
    from ..ruyipkg.repo import MetadataRepo
    from ..ruyipkg.state import RuyipkgGlobalStateStore
    from ..telemetry.provider import TelemetryProvider
    from ..utils.global_mode import ProvidesGlobalMode
    from ..utils.xdg_basedir import XDGPathEntry
    from .news import NewsReadStatusStore

from . import errors
from . import schema


if sys.platform == "linux":
    PRESET_GLOBAL_CONFIG_LOCATIONS: Final[list[str]] = [
        # TODO: enable distro packagers to customize the $PREFIX to suit their
        # particular FS layout if necessary.
        "/usr/share/ruyi/config.toml",
        "/usr/local/share/ruyi/config.toml",
    ]
else:
    PRESET_GLOBAL_CONFIG_LOCATIONS: Final[list[str]] = []

DEFAULT_APP_NAME: Final = "ruyi"
DEFAULT_REPO_URL: Final = "https://github.com/ruyisdk/packages-index.git"
DEFAULT_REPO_BRANCH: Final = "main"
DEFAULT_TELEMETRY_MODE: Final = "local"  # "off", "local", "on"


def get_host_path_fragment_for_binary_install_dir(canonicalized_host: str) -> str:
    # e.g. linux/amd64 -> amd64; "windows/amd64" -> "windows-amd64"
    if canonicalized_host.startswith("linux/"):
        return canonicalized_host[6:]
    return canonicalized_host.replace("/", "-")


def _get_lang_code() -> str:
    lang = locale.getlocale()[0]
    return lang or "en_US"


class GlobalConfigPackagesType(TypedDict):
    prereleases: "NotRequired[bool]"


class GlobalConfigRepoType(TypedDict):
    local: "NotRequired[str]"
    remote: "NotRequired[str]"
    branch: "NotRequired[str]"


class GlobalConfigInstallationType(TypedDict):
    # Undocumented: whether this Ruyi installation is externally managed.
    #
    # Can be used by distro packagers (by placing a config file in /etc/xdg/ruyi)
    # to signify this status to an official Ruyi build (where IS_PACKAGED is
    # True), to prevent e.g. accidental self-uninstallation.
    externally_managed: "NotRequired[bool]"


class GlobalConfigTelemetryType(TypedDict):
    mode: "NotRequired[str]"
    upload_consent: "NotRequired[datetime.datetime | str]"
    pm_telemetry_url: "NotRequired[str]"


class GlobalConfigRootType(TypedDict):
    installation: "NotRequired[GlobalConfigInstallationType]"
    packages: "NotRequired[GlobalConfigPackagesType]"
    repo: "NotRequired[GlobalConfigRepoType]"
    telemetry: "NotRequired[GlobalConfigTelemetryType]"


class GlobalConfig:
    def __init__(self, gm: "ProvidesGlobalMode", logger: "RuyiLogger") -> None:
        from ..utils.xdg_basedir import XDGBaseDir

        self._gm = gm
        self.logger = logger

        # all defaults
        self.override_repo_dir: str | None = None
        self.override_repo_url: str | None = None
        self.override_repo_branch: str | None = None
        self.include_prereleases = False
        self.is_installation_externally_managed = False

        self._lang_code = _get_lang_code()

        self._dirs = XDGBaseDir(DEFAULT_APP_NAME)

        self._telemetry_mode: str | None = None
        self._telemetry_upload_consent: datetime.datetime | None = None
        self._telemetry_pm_telemetry_url: str | None = None

    def _apply_config(
        self,
        config_data: GlobalConfigRootType,
        *,
        is_global_scope: bool,
    ) -> None:
        if ins_cfg := config_data.get(schema.SECTION_INSTALLATION):
            iem = ins_cfg.get(schema.KEY_INSTALLATION_EXTERNALLY_MANAGED, None)
            if iem is not None and not is_global_scope:
                iem_cfg_key = f"{schema.SECTION_INSTALLATION}.{schema.KEY_INSTALLATION_EXTERNALLY_MANAGED}"
                self.logger.W(
                    f"the config key [yellow]{iem_cfg_key}[/] cannot be set from user config; ignoring",
                )
            else:
                self.is_installation_externally_managed = bool(iem)

        if pkgs_cfg := config_data.get(schema.SECTION_PACKAGES):
            self.include_prereleases = pkgs_cfg.get(
                schema.KEY_PACKAGES_PRERELEASES, False
            )

        if repo_cfg := config_data.get(schema.SECTION_REPO):
            self.override_repo_dir = repo_cfg.get(schema.KEY_REPO_LOCAL, None)
            self.override_repo_url = repo_cfg.get(schema.KEY_REPO_REMOTE, None)
            self.override_repo_branch = repo_cfg.get(schema.KEY_REPO_BRANCH, None)

            if self.override_repo_dir:
                if not pathlib.Path(self.override_repo_dir).is_absolute():
                    self.logger.W(
                        f"the local repo path '{self.override_repo_dir}' is not absolute; ignoring"
                    )
                    self.override_repo_dir = None

        if tele_cfg := config_data.get(schema.SECTION_TELEMETRY):
            self._telemetry_mode = tele_cfg.get(schema.KEY_TELEMETRY_MODE, None)
            self._telemetry_pm_telemetry_url = tele_cfg.get(
                schema.KEY_TELEMETRY_PM_TELEMETRY_URL,
                None,
            )

            self._telemetry_upload_consent = None
            if consent := tele_cfg.get(schema.KEY_TELEMETRY_UPLOAD_CONSENT, None):
                if isinstance(consent, datetime.datetime):
                    self._telemetry_upload_consent = consent

    def get_by_key(self, key: str | Sequence[str]) -> object:
        parsed_key = schema.parse_config_key(key)
        section, sel = parsed_key[0], parsed_key[1:]
        attr_name = self._get_attr_name_by_key(section, sel)
        if attr_name is None:
            raise errors.InvalidConfigKeyError(key)
        return getattr(self, attr_name)

    def set_by_key(self, key: str | Sequence[str], value: object) -> None:
        # We don't have to check for global-only keys here because this
        # method is only used for programmatic changes to the in-memory
        # config, not for loading from config files.
        parsed_key = schema.parse_config_key(key)
        section, sel = parsed_key[0], parsed_key[1:]
        attr_name = self._get_attr_name_by_key(section, sel)
        if attr_name is None:
            raise errors.InvalidConfigKeyError(key)
        schema.ensure_valid_config_kv(key, True, value)
        setattr(self, attr_name, value)

    @classmethod
    def _get_attr_name_by_key(cls, section: str, sel: list[str]) -> str | None:
        if section == schema.SECTION_INSTALLATION:
            return cls._get_section_installation(sel)
        elif section == schema.SECTION_PACKAGES:
            return cls._get_section_packages(sel)
        elif section == schema.SECTION_REPO:
            return cls._get_section_repo(sel)
        elif section == schema.SECTION_TELEMETRY:
            return cls._get_section_telemetry(sel)
        else:
            return None

    @classmethod
    def _get_section_installation(cls, selector: list[str]) -> str | None:
        if len(selector) != 1:
            return None
        leaf = selector[0]
        if leaf == schema.KEY_INSTALLATION_EXTERNALLY_MANAGED:
            return "is_installation_externally_managed"
        else:
            return None

    @classmethod
    def _get_section_packages(cls, selector: list[str]) -> str | None:
        if len(selector) != 1:
            return None
        leaf = selector[0]
        if leaf == schema.KEY_PACKAGES_PRERELEASES:
            return "include_prereleases"
        else:
            return None

    @classmethod
    def _get_section_repo(cls, selector: list[str]) -> str | None:
        if len(selector) != 1:
            return None
        leaf = selector[0]
        if leaf == schema.KEY_REPO_BRANCH:
            return "override_repo_branch"
        elif leaf == schema.KEY_REPO_LOCAL:
            return "override_repo_dir"
        elif leaf == schema.KEY_REPO_REMOTE:
            return "override_repo_url"
        else:
            return None

    @classmethod
    def _get_section_telemetry(cls, selector: list[str]) -> str | None:
        if len(selector) != 1:
            return None
        leaf = selector[0]
        if leaf == schema.KEY_TELEMETRY_MODE:
            return "telemetry_mode"
        elif leaf == schema.KEY_TELEMETRY_PM_TELEMETRY_URL:
            return "override_pm_telemetry_url"
        elif leaf == schema.KEY_TELEMETRY_UPLOAD_CONSENT:
            return "telemetry_upload_consent_time"
        else:
            return None

    @property
    def argv0(self) -> str:
        return self._gm.argv0

    @property
    def main_file(self) -> str:
        return self._gm.main_file

    @property
    def self_exe(self) -> str:
        return self._gm.self_exe

    @property
    def is_debug(self) -> bool:
        return self._gm.is_debug

    @property
    def is_experimental(self) -> bool:
        return self._gm.is_experimental

    @property
    def is_packaged(self) -> bool:
        return self._gm.is_packaged

    @property
    def is_porcelain(self) -> bool:
        return self._gm.is_porcelain

    @property
    def is_telemetry_optout(self) -> bool:
        return self._gm.is_telemetry_optout

    @property
    def is_cli_autocomplete(self) -> bool:
        return self._gm.is_cli_autocomplete

    @property
    def venv_root(self) -> str | None:
        return self._gm.venv_root

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

    @cached_property
    def news_read_status(self) -> "NewsReadStatusStore":
        from .news import NewsReadStatusStore

        filename = os.path.join(self.ensure_state_dir(), "news.read.txt")
        return NewsReadStatusStore(filename)

    @property
    def telemetry_root(self) -> os.PathLike[Any]:
        return pathlib.Path(self.ensure_state_dir()) / "telemetry"

    @property
    def telemetry(self) -> "TelemetryProvider | None":
        return None if self.telemetry_mode == "off" else self._telemetry_provider

    @cached_property
    def _telemetry_provider(self) -> "TelemetryProvider | None":
        """Do not access directly; use the ``telemetry`` property instead."""

        from ..telemetry.provider import TelemetryProvider

        return None if self.telemetry_mode == "off" else TelemetryProvider(self)

    @property
    def telemetry_mode(self) -> str:
        return self._telemetry_mode or DEFAULT_TELEMETRY_MODE

    @telemetry_mode.setter
    def telemetry_mode(self, mode: str) -> None:
        if mode not in ("off", "local", "on"):
            raise ValueError("telemetry mode must be one of: off, local, on")
        if self._gm.is_telemetry_optout and mode != "off":
            raise ValueError(
                "cannot enable telemetry when the environment variable opt-out is set"
            )
        self._telemetry_mode = mode

    @property
    def telemetry_upload_consent_time(self) -> datetime.datetime | None:
        return self._telemetry_upload_consent

    @telemetry_upload_consent_time.setter
    def telemetry_upload_consent_time(self, t: datetime.datetime | None) -> None:
        self._telemetry_upload_consent = t

    @property
    def override_pm_telemetry_url(self) -> str | None:
        return self._telemetry_pm_telemetry_url

    @override_pm_telemetry_url.setter
    def override_pm_telemetry_url(self, url: str | None) -> None:
        self._telemetry_pm_telemetry_url = url

    @cached_property
    def default_repo_dir(self) -> str:
        return os.path.join(self.cache_root, "packages-index")

    def get_repo_dir(self) -> str:
        return self.override_repo_dir or self.default_repo_dir

    @cached_property
    def have_overridden_repo_dir(self) -> bool:
        if not self.override_repo_dir:
            return False
        override_path = pathlib.Path(self.override_repo_dir)
        default_path = pathlib.Path(self.default_repo_dir)
        # we don't use samefile() here because the path may not exist
        return override_path.resolve() != default_path.resolve()

    def get_repo_url(self) -> str:
        return self.override_repo_url or DEFAULT_REPO_URL

    def get_repo_branch(self) -> str:
        return self.override_repo_branch or DEFAULT_REPO_BRANCH

    @cached_property
    def repo(self) -> "MetadataRepo":
        from ..ruyipkg.repo import MetadataRepo

        return MetadataRepo(self)

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
        for data_dir in self._dirs.app_data_dirs:
            p = data_dir.path / "binaries" / host_path / slug
            if p.exists():
                return p
        return None

    @property
    def ruyipkg_state_root(self) -> os.PathLike[Any]:
        return pathlib.Path(self.ensure_state_dir()) / "ruyipkg"

    @cached_property
    def ruyipkg_global_state(self) -> "RuyipkgGlobalStateStore":
        from ..ruyipkg.state import RuyipkgGlobalStateStore

        return RuyipkgGlobalStateStore(self.ruyipkg_state_root)

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

    def iter_preset_configs(self) -> "Iterable[XDGPathEntry]":
        """
        Yields possible Ruyi config files in all preset config path locations,
        sorted by precedence from lowest to highest (so that each file may be
        simply applied consecutively).
        """

        from ..utils.xdg_basedir import XDGPathEntry

        for path in PRESET_GLOBAL_CONFIG_LOCATIONS:
            yield XDGPathEntry(pathlib.Path(path), True)

    def iter_xdg_configs(self) -> "Iterable[XDGPathEntry]":
        """
        Yields possible Ruyi config files in all XDG config paths, sorted by precedence
        from lowest to highest (so that each file may be simply applied consecutively).
        """

        from ..utils.xdg_basedir import XDGPathEntry

        entries = list(self._dirs.app_config_dirs)
        for e in reversed(entries):
            yield XDGPathEntry(e.path / "config.toml", e.is_global)

    @property
    def local_user_config_file(self) -> pathlib.Path:
        return self._dirs.app_config / "config.toml"

    def _try_apply_config_file(
        self,
        path: os.PathLike[Any],
        *,
        is_global_scope: bool,
    ) -> None:
        import tomlkit

        try:
            with open(path, "rb") as fp:
                data: Any = tomlkit.load(fp)
        except FileNotFoundError:
            return

        self.logger.D(f"applying config: {data}, is_global_scope={is_global_scope}")
        self._apply_config(data, is_global_scope=is_global_scope)

    @classmethod
    def load_from_config(cls, gm: "ProvidesGlobalMode", logger: "RuyiLogger") -> "Self":
        obj = cls(gm, logger)

        for config_path, is_global in obj.iter_preset_configs():
            obj.logger.D(f"trying config file from preset location: {config_path}")
            obj._try_apply_config_file(config_path, is_global_scope=is_global)

        for config_path, is_global in obj.iter_xdg_configs():
            obj.logger.D(f"trying config file from XDG path: {config_path}")
            obj._try_apply_config_file(config_path, is_global_scope=is_global)

        # let environment variable take precedence
        if gm.is_telemetry_optout:
            obj._telemetry_mode = "off"
            obj._telemetry_upload_consent = None

        return obj
