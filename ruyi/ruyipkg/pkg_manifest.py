from functools import cached_property
import os
import platform
import re
from typing import Iterable, Literal, NotRequired, TypedDict

from semver.version import Version


class VendorDeclType(TypedDict):
    name: str
    eula: str | None


class DistfileDeclType(TypedDict):
    name: str
    size: int
    checksums: dict[str, str]
    strip_components: NotRequired[int]


class BinaryFileDeclType(TypedDict):
    host: str
    distfiles: list[str]


BinaryDeclType = list[BinaryFileDeclType]


class SourceDeclType(TypedDict):
    distfiles: list[str]


class ToolchainComponentDeclType(TypedDict):
    name: str
    version: str


class ToolchainDeclType(TypedDict):
    target: str
    flavors: list[str]
    components: list[ToolchainComponentDeclType]
    included_sysroot: NotRequired[str]


EmulatorFlavor = Literal["qemu-linux-user"]


class EmulatorProgramDeclType(TypedDict):
    path: str
    flavor: EmulatorFlavor
    supported_arches: list[str]
    binfmt_misc: NotRequired[str]


class EmulatorDeclType(TypedDict):
    flavors: NotRequired[list[str]]
    programs: list[EmulatorProgramDeclType]


PackageKind = (
    Literal["binary"] | Literal["source"] | Literal["toolchain"] | Literal["emulator"]
)


class PackageManifestType(TypedDict):
    slug: NotRequired[str]
    kind: list[PackageKind]
    desc: str
    doc_uri: NotRequired[str]
    vendor: VendorDeclType
    distfiles: list[DistfileDeclType]
    binary: NotRequired[BinaryDeclType]
    source: NotRequired[SourceDeclType]
    toolchain: NotRequired[ToolchainDeclType]
    emulator: NotRequired[EmulatorDeclType]


class DistfileDecl:
    def __init__(self, data: DistfileDeclType) -> None:
        self._data = data

    @property
    def name(self) -> str:
        return self._data["name"]

    @property
    def size(self) -> int:
        return self._data["size"]

    @property
    def checksums(self) -> dict[str, str]:
        return self._data["checksums"]

    def get_checksum(self, kind: str) -> str | None:
        return self._data["checksums"].get(kind)

    @property
    def strip_components(self) -> int:
        return self._data.get("strip_components", 1)


class BinaryDecl:
    def __init__(self, data: BinaryDeclType) -> None:
        self._data = {d["host"]: d["distfiles"] for d in data}

    @property
    def data(self) -> dict[str, list[str]]:
        return self._data

    def get_distfile_names_for_host(self, host: str) -> list[str] | None:
        return self._data.get(host)

    @property
    def is_available_for_current_host(self) -> bool:
        return platform.machine() in self._data


class SourceDecl:
    def __init__(self, data: SourceDeclType) -> None:
        self._data = data

    def get_distfile_names_for_host(self, host: str) -> list[str] | None:
        # currently the host parameter is ignored
        return self._data["distfiles"]


class ToolchainDecl:
    def __init__(self, data: ToolchainDeclType) -> None:
        self._data = data
        self._component_vers_cache: dict[str, str] | None = None

    @property
    def _component_vers(self) -> dict[str, str]:
        if self._component_vers_cache is None:
            self._component_vers_cache = {
                x["name"]: x["version"] for x in self.components
            }
        return self._component_vers_cache

    @property
    def target(self) -> str:
        return self._data["target"]

    @property
    def target_arch(self) -> str:
        # TODO: switch to proper mapping later; for now this suffices
        return self.target.split("-", 1)[0]

    @property
    def flavors(self) -> list[str]:
        return self._data["flavors"]

    def has_flavor(self, f: str) -> bool:
        return f in self._data["flavors"]

    def satisfies_flavor_set(self, req: set[str]) -> bool:
        # req - my_flavors must be the empty set so that my_flavors >= req
        return len(req.difference(self.flavors)) == 0

    @property
    def components(self) -> Iterable[ToolchainComponentDeclType]:
        return self._data["components"]

    def get_component_version(self, name: str) -> str | None:
        return self._component_vers.get(name)

    @property
    def has_binutils(self) -> bool:
        return self.get_component_version("binutils") is not None

    @property
    def has_clang(self) -> bool:
        return self.get_component_version("clang") is not None

    @property
    def has_gcc(self) -> bool:
        return self.get_component_version("gcc") is not None

    @property
    def has_llvm(self) -> bool:
        return self.get_component_version("llvm") is not None

    @property
    def included_sysroot(self) -> str | None:
        return self._data.get("included_sysroot")


class EmulatorProgDecl:
    def __init__(self, data: EmulatorProgramDeclType) -> None:
        self.relative_path = data["path"]
        # have to explicitly annotate the type to please the type checker...
        self.flavor: EmulatorFlavor = data["flavor"]
        self.supported_arches = set(data["supported_arches"])
        self.binfmt_misc = data.get("binfmt_misc")

    def get_binfmt_misc_str(self, install_root: os.PathLike) -> str | None:
        if self.binfmt_misc is None:
            return None
        binpath = os.path.join(install_root, self.relative_path)
        return self.binfmt_misc.replace("$BIN", binpath)

    @property
    def is_qemu(self) -> bool:
        return self.flavor == "qemu-linux-user"


class EmulatorDecl:
    def __init__(self, data: EmulatorDeclType) -> None:
        self._data = data
        self.programs = [EmulatorProgDecl(x) for x in data["programs"]]

    @property
    def flavors(self) -> list[str] | None:
        return self._data.get("flavors")

    def list_for_arch(self, arch: str) -> Iterable[EmulatorProgDecl]:
        for p in self.programs:
            if arch in p.supported_arches:
                yield p


class PackageManifest:
    def __init__(
        self,
        category: str,
        name: str,
        ver: str,
        data: PackageManifestType,
    ) -> None:
        self._data = data
        self.category = category
        self.name = name
        self.ver = ver
        self._semver = Version.parse(ver)

    @property
    def semver(self) -> Version:
        return self._semver

    @property
    def is_prerelease(self) -> bool:
        return is_prerelease(self._semver)

    @property
    def slug(self) -> str | None:
        return self._data.get("slug")

    @property
    def name_for_installation(self) -> str:
        return f"{self.name}-{self.ver}"

    @property
    def kind(self) -> list[PackageKind]:
        return self._data["kind"]

    def has_kind(self, k: PackageKind) -> bool:
        return k in self._data["kind"]

    @property
    def desc(self) -> str:
        return self._data["desc"]

    @property
    def doc_uri(self) -> str | None:
        return self._data.get("doc_uri")

    @property
    def vendor_name(self) -> str:
        return self._data["vendor"]["name"]

    # TODO: vendor_eula

    def distfiles(self) -> dict[str, DistfileDecl]:
        return {x["name"]: DistfileDecl(x) for x in self._data["distfiles"]}

    @cached_property
    def binary_metadata(self) -> BinaryDecl | None:
        if not self.has_kind("binary"):
            return None
        if "binary" not in self._data:
            return None
        return BinaryDecl(self._data["binary"])

    @cached_property
    def source_metadata(self) -> SourceDecl | None:
        if not self.has_kind("source"):
            return None
        if "source" not in self._data:
            return None
        return SourceDecl(self._data["source"])

    @cached_property
    def toolchain_metadata(self) -> ToolchainDecl | None:
        if not self.has_kind("toolchain"):
            return None
        if "toolchain" not in self._data:
            return None
        return ToolchainDecl(self._data["toolchain"])

    @cached_property
    def emulator_metadata(self) -> EmulatorDecl | None:
        if not self.has_kind("emulator"):
            return None
        if "emulator" not in self._data:
            return None
        return EmulatorDecl(self._data["emulator"])


RUYI_DATESTAMP_IN_SEMVER_RE = re.compile(r"^ruyi\.\d+$")


def is_prerelease(sv: Version) -> bool:
    if sv.prerelease is None:
        return False

    # don't consider "ruyi.*" versions as prerelease
    # if the prerelease string only contains a "ruyi.\d+" part, then that's
    # considered as just a datestamp, and not a prerelease in ruyi's interpretation.
    return RUYI_DATESTAMP_IN_SEMVER_RE.match(sv.prerelease) is None
