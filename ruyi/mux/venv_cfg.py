import copy
import os.path
import pathlib
import sys
from typing import Any, TypedDict, TYPE_CHECKING, cast

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

if TYPE_CHECKING:
    from typing_extensions import NotRequired, Self


from ..log import RuyiLogger
from ..utils.global_mode import ProvidesGlobalMode


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
    def explicit_ruyi_venv_root(cls, gm: ProvidesGlobalMode) -> str | None:
        return gm.venv_root

    @classmethod
    def probe_venv_root(cls, gm: ProvidesGlobalMode) -> pathlib.Path | None:
        if explicit_root := cls.explicit_ruyi_venv_root(gm):
            return pathlib.Path(explicit_root)

        # check ../.. from argv[0]
        # this only works if it contains a path separator, otherwise it's really
        # hard without an explicit root (/proc/*/exe points to the resolved file,
        # but we want the path to the first symlink without any symlink dereference)
        argv0_path = gm.argv0
        if os.path.sep not in argv0_path:
            return None

        implied_root = pathlib.Path(os.path.dirname(os.path.dirname(argv0_path)))
        if (implied_root / "ruyi-venv.toml").exists():
            return implied_root

        return None

    @classmethod
    def load_from_venv(
        cls,
        gm: ProvidesGlobalMode,
        logger: RuyiLogger,
    ) -> "Self | None":
        venv_root = cls.probe_venv_root(gm)
        if venv_root is None:
            return None

        if cls.explicit_ruyi_venv_root(gm) is not None:
            logger.D(f"using explicit venv root {venv_root}")
        else:
            logger.D(f"detected implicit venv root {venv_root}")

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
