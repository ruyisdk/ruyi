import copy
import datetime
import locale
import os.path
from os import PathLike
import pathlib
import sys
from typing import Any, Final, Iterable, Sequence, TypedDict, TYPE_CHECKING, cast

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

if TYPE_CHECKING:
    from typing_extensions import NotRequired, Self

import tomlkit

from .. import argv0, is_env_var_truthy, log
from ..ruyipkg.repo import MetadataRepo
from ..telemetry import TelemetryStore
from ..utils.xdg_basedir import XDGBaseDir
from .news import NewsReadStatusStore
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

ENV_TELEMETRY_OPTOUT_KEY: Final = "RUYI_TELEMETRY_OPTOUT"
ENV_VENV_ROOT_KEY: Final = "RUYI_VENV"


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
    def __init__(self) -> None:
        # all defaults
        self.override_repo_dir: str | None = None
        self.override_repo_url: str | None = None
        self.override_repo_branch: str | None = None
        self.include_prereleases = False
        self.is_installation_externally_managed = False

        self._metadata_repo: MetadataRepo | None = None
        self._news_read_status_store: NewsReadStatusStore | None = None
        self._telemetry_store: TelemetryStore | None = None

        self._lang_code = _get_lang_code()

        self._dirs = XDGBaseDir(DEFAULT_APP_NAME)

        self._telemetry_mode: str | None = None
        self._telemetry_upload_consent: datetime.datetime | None = None
        self._telemetry_pm_telemetry_url: str | None = None

    def apply_config(self, config_data: GlobalConfigRootType) -> None:
        if ins_cfg := config_data.get(schema.SECTION_INSTALLATION):
            self.is_installation_externally_managed = ins_cfg.get(
                schema.KEY_INSTALLATION_EXTERNALLY_MANAGED,
                False,
            )

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
                    log.W(
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

    def get_by_key(self, key: str | Sequence[str]) -> object | None:
        parsed_key = schema.parse_config_key(key)
        section, sel = parsed_key[0], parsed_key[1:]
        if section == schema.SECTION_INSTALLATION:
            return self._get_section_installation(sel)
        elif section == schema.SECTION_PACKAGES:
            return self._get_section_packages(sel)
        elif section == schema.SECTION_REPO:
            return self._get_section_repo(sel)
        elif section == schema.SECTION_TELEMETRY:
            return self._get_section_telemetry(sel)
        else:
            return None

    def _get_section_installation(self, selector: list[str]) -> object | None:
        if len(selector) != 1:
            return None
        leaf = selector[0]
        if leaf == schema.KEY_INSTALLATION_EXTERNALLY_MANAGED:
            return self.is_installation_externally_managed
        else:
            return None

    def _get_section_packages(self, selector: list[str]) -> object | None:
        if len(selector) != 1:
            return None
        leaf = selector[0]
        if leaf == schema.KEY_PACKAGES_PRERELEASES:
            return self.include_prereleases
        else:
            return None

    def _get_section_repo(self, selector: list[str]) -> object | None:
        if len(selector) != 1:
            return None
        leaf = selector[0]
        if leaf == schema.KEY_REPO_BRANCH:
            return self.override_repo_branch
        elif leaf == schema.KEY_REPO_LOCAL:
            return self.override_repo_dir
        elif leaf == schema.KEY_REPO_REMOTE:
            return self.override_repo_url
        else:
            return None

    def _get_section_telemetry(self, selector: list[str]) -> object | None:
        if len(selector) != 1:
            return None
        leaf = selector[0]
        if leaf == schema.KEY_TELEMETRY_MODE:
            return self.telemetry_mode
        elif leaf == schema.KEY_TELEMETRY_PM_TELEMETRY_URL:
            return self.override_pm_telemetry_url
        elif leaf == schema.KEY_TELEMETRY_UPLOAD_CONSENT:
            return self.telemetry_upload_consent_time
        else:
            return None

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

    @property
    def telemetry_root(self) -> os.PathLike[Any]:
        return pathlib.Path(self.ensure_state_dir()) / "telemetry"

    @property
    def telemetry(self) -> TelemetryStore | None:
        if self.telemetry_mode == "off":
            return None
        if self._telemetry_store is not None:
            return self._telemetry_store

        self._telemetry_store = TelemetryStore(self)
        return self._telemetry_store

    @property
    def telemetry_mode(self) -> str:
        return self._telemetry_mode or "on"

    @property
    def telemetry_upload_consent_time(self) -> datetime.datetime | None:
        return self._telemetry_upload_consent

    @property
    def override_pm_telemetry_url(self) -> str | None:
        return self._telemetry_pm_telemetry_url

    def get_repo_dir(self) -> str:
        return self.override_repo_dir or os.path.join(self.cache_root, "packages-index")

    def get_repo_url(self) -> str:
        return self.override_repo_url or DEFAULT_REPO_URL

    def get_repo_branch(self) -> str:
        return self.override_repo_branch or DEFAULT_REPO_BRANCH

    @property
    def repo(self) -> MetadataRepo:
        if self._metadata_repo is not None:
            return self._metadata_repo
        self._metadata_repo = MetadataRepo(self)
        return self._metadata_repo

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

    def iter_preset_configs(self) -> Iterable[os.PathLike[Any]]:
        """
        Yields possible Ruyi config files in all preset config path locations,
        sorted by precedence from lowest to highest (so that each file may be
        simply applied consecutively).
        """

        for path in PRESET_GLOBAL_CONFIG_LOCATIONS:
            yield pathlib.Path(path)

    def iter_xdg_configs(self) -> Iterable[os.PathLike[Any]]:
        """
        Yields possible Ruyi config files in all XDG config paths, sorted by precedence
        from lowest to highest (so that each file may be simply applied consecutively).
        """

        for config_dir in reversed(list(self._dirs.app_config_dirs)):
            yield config_dir / "config.toml"

    @property
    def local_user_config_file(self) -> pathlib.Path:
        return self._dirs.app_config / "config.toml"

    def try_apply_config_file(self, path: os.PathLike[Any]) -> None:
        try:
            with open(path, "rb") as fp:
                data: Any = tomlkit.load(fp)
        except FileNotFoundError:
            return

        log.D(f"applying config: {data}")
        self.apply_config(data)

    @classmethod
    def load_from_config(cls) -> "Self":
        obj = cls()

        for config_path in obj.iter_preset_configs():
            log.D(f"trying config file from preset location: {config_path}")
            obj.try_apply_config_file(config_path)

        for config_path in obj.iter_xdg_configs():
            log.D(f"trying config file from XDG path: {config_path}")
            obj.try_apply_config_file(config_path)

        # let environment variable take precedence
        if is_env_var_truthy(ENV_TELEMETRY_OPTOUT_KEY):
            obj._telemetry_mode = "off"

        return obj


class VenvConfigType(TypedDict):
    profile: str
    sysroot: "NotRequired[str]"


class VenvConfigRootType(TypedDict):
    config: VenvConfigType


class VenvCacheV0Type(TypedDict):
    target_tuple: str
    toolchain_bindir: str
    gcc_install_dir: "NotRequired[str]"
    profile_common_flags: str
    qemu_bin: "NotRequired[str]"
    profile_emu_env: "NotRequired[dict[str, str]]"


class VenvCacheV1TargetType(TypedDict):
    toolchain_bindir: str
    toolchain_sysroot: "NotRequired[str]"
    gcc_install_dir: "NotRequired[str]"


class VenvCacheV2TargetType(VenvCacheV1TargetType):
    toolchain_flags: str


class VenvCacheV1CmdMetadataEntryType(TypedDict):
    dest: str
    target_tuple: str


class VenvCacheV1Type(TypedDict):
    profile_common_flags: str
    profile_emu_env: "NotRequired[dict[str, str]]"
    qemu_bin: "NotRequired[str]"
    targets: dict[str, VenvCacheV1TargetType]
    cmd_metadata_map: "NotRequired[dict[str, VenvCacheV1CmdMetadataEntryType]]"


class VenvCacheV2Type(TypedDict):
    profile_emu_env: "NotRequired[dict[str, str]]"
    qemu_bin: "NotRequired[str]"
    targets: dict[str, VenvCacheV2TargetType]
    cmd_metadata_map: "NotRequired[dict[str, VenvCacheV1CmdMetadataEntryType]]"


class VenvCacheRootType(TypedDict):
    cached: "NotRequired[VenvCacheV0Type]"
    cached_v1: "NotRequired[VenvCacheV1Type]"
    cached_v2: "NotRequired[VenvCacheV2Type]"


def parse_venv_cache(
    cache: VenvCacheRootType,
    global_sysroot: str | None,
) -> VenvCacheV2Type:
    if "cached_v2" in cache:
        return cache["cached_v2"]
    if "cached_v1" in cache:
        return upgrade_venv_cache_v1(cache["cached_v1"])
    if "cached" in cache:
        return upgrade_venv_cache_v0(cache["cached"], global_sysroot)
    raise RuntimeError("unsupported venv cache version")


def upgrade_venv_cache_v1(x: VenvCacheV1Type) -> VenvCacheV2Type:
    profile_common_flags = x["profile_common_flags"]
    tmp = cast(dict[str, Any], copy.deepcopy(x))
    del tmp["profile_common_flags"]
    v2 = cast(VenvCacheV2Type, tmp)
    for tgt in v2["targets"].values():
        tgt["toolchain_flags"] = profile_common_flags
    return v2


def upgrade_venv_cache_v0(
    x: VenvCacheV0Type,
    global_sysroot: str | None,
) -> VenvCacheV2Type:
    # v0 only supports one single target so upgrading is trivial
    v1_target: VenvCacheV1TargetType = {
        "toolchain_bindir": x["toolchain_bindir"],
    }
    if "gcc_install_dir" in x:
        v1_target["gcc_install_dir"] = x["gcc_install_dir"]
    if global_sysroot is not None:
        v1_target["toolchain_sysroot"] = global_sysroot

    y: VenvCacheV1Type = {
        "profile_common_flags": x["profile_common_flags"],
        "targets": {x["target_tuple"]: v1_target},
    }
    if "profile_emu_env" in x:
        y["profile_emu_env"] = x["profile_emu_env"]
    if "qemu_bin" in x:
        y["qemu_bin"] = x["qemu_bin"]

    return upgrade_venv_cache_v1(y)


class RuyiVenvConfig:
    def __init__(
        self,
        venv_root: pathlib.Path,
        cfg: VenvConfigRootType,
        cache: VenvCacheRootType,
    ) -> None:
        self.venv_root = venv_root
        self.profile = cfg["config"]["profile"]
        self.sysroot = cfg["config"].get("sysroot")

        parsed_cache = parse_venv_cache(cache, self.sysroot)
        self.targets = parsed_cache["targets"]
        self.qemu_bin = parsed_cache.get("qemu_bin")
        self.profile_emu_env = parsed_cache.get("profile_emu_env")
        self.cmd_metadata_map = parsed_cache.get("cmd_metadata_map")

        # this must be in sync with provision.py
        self._ruyi_priv_dir = self.venv_root / "ruyi-private"
        self._cached_cmd_targets_dir = self._ruyi_priv_dir / "cached-cmd-targets"

    @classmethod
    def explicit_ruyi_venv_root(cls) -> str | None:
        return os.environ.get(ENV_VENV_ROOT_KEY)

    @classmethod
    def probe_venv_root(cls) -> pathlib.Path | None:
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
    def load_from_venv(cls) -> "Self | None":
        venv_root = cls.probe_venv_root()
        if venv_root is None:
            return None

        if cls.explicit_ruyi_venv_root() is not None:
            log.D(f"using explicit venv root {venv_root}")
        else:
            log.D(f"detected implicit venv root {venv_root}")

        venv_config_path = venv_root / "ruyi-venv.toml"
        with open(venv_config_path, "rb") as fp:
            cfg: Any = tomllib.load(fp)  # in order to cast to our stricter type

        cache: Any  # in order to cast to our stricter type
        venv_cache_v2_path = venv_root / "ruyi-cache.v2.toml"
        try:
            with open(venv_cache_v2_path, "rb") as fp:
                cache = tomllib.load(fp)
        except FileNotFoundError:
            venv_cache_v1_path = venv_root / "ruyi-cache.v1.toml"
            try:
                with open(venv_cache_v1_path, "rb") as fp:
                    cache = tomllib.load(fp)
            except FileNotFoundError:
                venv_cache_v0_path = venv_root / "ruyi-cache.toml"
                with open(venv_cache_v0_path, "rb") as fp:
                    cache = tomllib.load(fp)

        # NOTE: for now it's not prohibited to have cache data of a different
        # version in a certain version's cache path, but this situation is
        # harmless
        return cls(venv_root, cfg, cache)

    def resolve_cmd_metadata_with_cache(
        self,
        basename: str,
    ) -> VenvCacheV1CmdMetadataEntryType | None:
        if self.cmd_metadata_map is None:
            # we are operating in a venv created with an older ruyi, thus no
            # cmd_metadata_map in cache
            return None

        return self.cmd_metadata_map.get(basename)
