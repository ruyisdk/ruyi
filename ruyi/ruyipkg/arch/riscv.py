from os import PathLike
from typing import Iterable, NotRequired, TypedDict

from ... import log
from ..pkg_manifest import EmulatorFlavor
from ..profile import (
    ArchProfileParser,
    ArchProfilesDeclType,
    ProfileDecl,
    ProfileDeclType,
    register_arch_profile_parser,
)


class RISCVGenericOpts(TypedDict):
    march: str
    mabi: str
    mcpu: NotRequired[str]


class RISCVProfileDeclType(ProfileDeclType):
    march: NotRequired[str]
    mabi: NotRequired[str]
    mcpu: NotRequired[str]


# dict[flavor, dict[generic-mcpu-name, flavor-mcpu-name]]
FlavorMCPUMap = dict[str, dict[str, str]]


class RISCVEmulatorPresetForFlavor(TypedDict):
    env: dict[str, str]


EmulatorPresetForCPU = dict[EmulatorFlavor, RISCVEmulatorPresetForFlavor]
# dict[mcpu-name, EmulatorPresetForCPU]
EmulatorPresets = dict[str, EmulatorPresetForCPU]


class RISCVArchProfilesDeclType(ArchProfilesDeclType):
    generic_opts: RISCVGenericOpts
    profiles: list[RISCVProfileDeclType]
    flavor_specific_mcpus: FlavorMCPUMap
    emulator_presets: EmulatorPresets


class RISCVProfileDecl(ProfileDecl):
    def __init__(
        self,
        arch: str,
        decl: RISCVProfileDeclType,
        generic_opts: RISCVGenericOpts,
        mcpu_map: FlavorMCPUMap,
        emulator_presets: EmulatorPresets,
    ) -> None:
        super().__init__(arch, decl)

        self.mabi = decl.get("mabi", generic_opts["mabi"])
        self.march = decl.get("march", generic_opts["march"])
        raw_mcpu = decl.get("mcpu", generic_opts.get("mcpu"))
        self.mcpu = raw_mcpu

        if self.mcpu is not None and self.need_flavor:
            # maybe our mcpu needs some substitution
            for fl in self.need_flavor:
                try:
                    self.mcpu = mcpu_map[fl][self.mcpu]
                except KeyError:
                    continue

        mcpu_for_emu = raw_mcpu if raw_mcpu is not None else "generic"
        self.emulator_cfg: EmulatorPresetForCPU | None = emulator_presets.get(
            mcpu_for_emu,
            emulator_presets.get("generic"),
        )

    def get_common_flags(self) -> str:
        if self.mcpu is not None:
            return f"-mcpu={self.mcpu} -mabi={self.mabi}"
        return f"-march={self.march} -mabi={self.mabi}"

    def get_env_config_for_emu_flavor(
        self,
        flavor: EmulatorFlavor,
        sysroot: PathLike | None,
    ) -> dict[str, str] | None:
        result = super().get_env_config_for_emu_flavor(flavor, sysroot)
        if result is None:
            result = {}

        if self.emulator_cfg is None:
            return result

        cfg_for_flavor = self.emulator_cfg.get(flavor)
        if cfg_for_flavor is None:
            return result

        if env := cfg_for_flavor.get("env"):
            result.update(env)

        return result


def parse_riscv_arch_profiles(
    arch: str,
    data: RISCVArchProfilesDeclType,
) -> Iterable[RISCVProfileDecl]:
    log.D(f"got data: {data}")
    generic_opts = data["generic_opts"]
    mcpu_map = data["flavor_specific_mcpus"]
    emulator_presets = data["emulator_presets"]

    # emit the generic profile
    yield RISCVProfileDecl(
        arch, {"name": "generic"}, generic_opts, mcpu_map, emulator_presets
    )

    # and the rest
    for p in data["profiles"]:
        yield RISCVProfileDecl(arch, p, generic_opts, mcpu_map, emulator_presets)


register_arch_profile_parser(parse_riscv_arch_profiles, "riscv32", "riscv64")
