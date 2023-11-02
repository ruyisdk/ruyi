from typing import Iterable, NotRequired, TypedDict

from ... import log
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


FlavorMCPUMap = dict[str, dict[str, str]]


class RISCVArchProfilesDeclType(ArchProfilesDeclType):
    generic_opts: RISCVGenericOpts
    profiles: list[RISCVProfileDeclType]

    # dict[flavor, dict[generic-mcpu-name, flavor-mcpu-name]]
    flavor_specific_mcpus: FlavorMCPUMap


class RISCVProfileDecl(ProfileDecl):
    def __init__(
        self,
        decl: RISCVProfileDeclType,
        generic_opts: RISCVGenericOpts,
        mcpu_map: FlavorMCPUMap,
    ) -> None:
        super().__init__(decl)

        self.mabi = decl.get("mabi", generic_opts["mabi"])
        self.march = decl.get("march", generic_opts["march"])
        self.mcpu = decl.get("mcpu", generic_opts.get("mcpu"))

        if self.mcpu is not None and self.need_flavor:
            # maybe our mcpu needs some substitution
            for fl in self.need_flavor:
                try:
                    self.mcpu = mcpu_map[fl][self.mcpu]
                except KeyError:
                    continue

    def get_common_flags(self) -> str:
        if self.mcpu is not None:
            return f"-mcpu={self.mcpu} -mabi={self.mabi}"
        return f"-march={self.march} -mabi={self.mabi}"


def parse_riscv_arch_profiles(
    data: RISCVArchProfilesDeclType,
) -> Iterable[RISCVProfileDecl]:
    log.D(f"got data: {data}")
    generic_opts = data["generic_opts"]
    mcpu_map = data["flavor_specific_mcpus"]

    # emit the generic profile
    yield RISCVProfileDecl({"name": "generic"}, generic_opts, mcpu_map)

    # and the rest
    for p in data["profiles"]:
        yield RISCVProfileDecl(p, generic_opts, mcpu_map)


register_arch_profile_parser(parse_riscv_arch_profiles, "riscv32", "riscv64")
