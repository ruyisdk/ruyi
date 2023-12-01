import re
from typing import Iterable, NotRequired, TypedDict

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


class PackageManifestType(TypedDict):
    slug: NotRequired[str]
    kind: list[str]
    desc: str
    doc_uri: NotRequired[str]
    vendor: VendorDeclType
    distfiles: list[DistfileDeclType]
    binary: NotRequired[BinaryDeclType]
    source: NotRequired[SourceDeclType]
    toolchain: NotRequired[ToolchainDeclType]


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
    def flavors(self) -> list[str]:
        return self._data["flavors"]

    def has_flavor(self, f: str) -> bool:
        return f in self._data["flavors"]

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
    def kind(self) -> list[str]:
        return self._data["kind"]

    def has_kind(self, k: str) -> bool:
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

    @property
    def binary_metadata(self) -> BinaryDecl | None:
        if not self.has_kind("binary"):
            return None
        if "binary" not in self._data:
            return None
        return BinaryDecl(self._data["binary"])

    @property
    def source_metadata(self) -> SourceDecl | None:
        if not self.has_kind("source"):
            return None
        if "source" not in self._data:
            return None
        return SourceDecl(self._data["source"])

    @property
    def toolchain_metadata(self) -> ToolchainDecl | None:
        if not self.has_kind("toolchain"):
            return None
        if "toolchain" not in self._data:
            return None
        return ToolchainDecl(self._data["toolchain"])


RUYI_DATESTAMP_IN_SEMVER_RE = re.compile(r"^ruyi\.\d+$")


def is_prerelease(sv: Version) -> bool:
    if sv.prerelease is None:
        return False

    # don't consider "ruyi.*" versions as prerelease
    # if the prerelease string only contains a "ruyi.\d+" part, then that's
    # considered as just a datestamp, and not a prerelease in ruyi's interpretation.
    return RUYI_DATESTAMP_IN_SEMVER_RE.match(sv.prerelease) is None
