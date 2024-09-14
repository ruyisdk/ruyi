from copy import deepcopy
from functools import cached_property
import json
import os
import pathlib
import re
import tomllib
from typing import Any, BinaryIO, Iterable, Literal, NotRequired, Self, TypedDict, cast

from semver.version import Version

from .host import canonicalize_host_str, get_native_host
from .unpack_method import UnpackMethod, determine_unpack_method


class VendorDeclType(TypedDict):
    name: str
    eula: str | None


RestrictKind = Literal["fetch"] | Literal["mirror"]


class FetchRestrictionDeclType(TypedDict):
    msgid: str
    params: NotRequired[dict[str, str]]


class DistfileDeclType(TypedDict):
    name: str
    urls: NotRequired[list[str]]
    restrict: NotRequired[list[RestrictKind]]
    size: int
    checksums: dict[str, str]
    strip_components: NotRequired[int]
    unpack: NotRequired[UnpackMethod]
    fetch_restriction: NotRequired[FetchRestrictionDeclType]


class BinaryFileDeclType(TypedDict):
    host: str
    distfiles: list[str]


BinaryDeclType = list[BinaryFileDeclType]


class BlobDeclType(TypedDict):
    distfiles: list[str]


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


PartitionKind = (
    Literal["boot"]
    | Literal["disk"]
    | Literal["live"]
    | Literal["root"]
    | Literal["uboot"]
)

# error: "<typing special form>" has no attribute "__args__"
# KNOWN_PARTITION_KINDS = frozenset(kind.__args__[0] for kind in PartitionKind.__args__)
KNOWN_PARTITION_KINDS = frozenset(("boot", "disk", "live", "root", "uboot"))

PartitionMapDecl = dict[PartitionKind, str]


class ProvisionableDeclType(TypedDict):
    partition_map: PartitionMapDecl
    strategy: str


PackageKind = (
    Literal["binary"]
    | Literal["blob"]
    | Literal["source"]
    | Literal["toolchain"]
    | Literal["emulator"]
    | Literal["provisionable"]
)

ALL_PACKAGE_KINDS: list[PackageKind] = [
    "binary",
    "blob",
    "source",
    "toolchain",
    "emulator",
    "provisionable",
]

RuyiPkgFormat = Literal["v1"]


class PackageMetadataDeclType(TypedDict):
    slug: NotRequired[str]  # deprecated for v1+
    desc: str
    doc_uri: NotRequired[str]
    vendor: VendorDeclType


class InputPackageManifestType(TypedDict):
    format: NotRequired[RuyiPkgFormat]

    # v0 fields
    slug: NotRequired[str]
    kind: NotRequired[list[PackageKind]]  # mandatory in v0
    desc: NotRequired[str]  # mandatory in v0
    doc_uri: NotRequired[str]
    vendor: NotRequired[VendorDeclType]  # mandatory in v0

    # v1+ fields
    metadata: NotRequired[PackageMetadataDeclType]

    # common fields
    distfiles: list[DistfileDeclType]
    binary: NotRequired[BinaryDeclType]
    blob: NotRequired[BlobDeclType]
    source: NotRequired[SourceDeclType]
    toolchain: NotRequired[ToolchainDeclType]
    emulator: NotRequired[EmulatorDeclType]
    provisionable: NotRequired[ProvisionableDeclType]


class PackageManifestType(TypedDict):
    format: RuyiPkgFormat
    kind: list[PackageKind]
    metadata: PackageMetadataDeclType
    distfiles: list[DistfileDeclType]
    binary: NotRequired[BinaryDeclType]
    blob: NotRequired[BlobDeclType]
    source: NotRequired[SourceDeclType]
    toolchain: NotRequired[ToolchainDeclType]
    emulator: NotRequired[EmulatorDeclType]
    provisionable: NotRequired[ProvisionableDeclType]


class DistfileDecl:
    def __init__(self, data: DistfileDeclType) -> None:
        self._data = data

    @property
    def name(self) -> str:
        return self._data["name"]

    @property
    def urls(self) -> list[str] | None:
        return self._data.get("urls")

    def is_restricted(self, kind: RestrictKind) -> bool:
        if restricts := self._data.get("restrict"):
            return kind in restricts
        return False

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

    @property
    def unpack_method(self) -> UnpackMethod:
        x = self._data.get("unpack", UnpackMethod.AUTO)
        if x == UnpackMethod.AUTO:
            return determine_unpack_method(self.name)
        return x

    @property
    def fetch_restriction(self) -> FetchRestrictionDeclType | None:
        return self._data.get("fetch_restriction")


class BinaryDecl:
    def __init__(self, data: BinaryDeclType) -> None:
        self._data = {canonicalize_host_str(d["host"]): d["distfiles"] for d in data}

    @property
    def data(self) -> dict[str, list[str]]:
        return self._data

    def get_distfile_names_for_host(self, host: str) -> list[str] | None:
        return self._data.get(canonicalize_host_str(host))

    @property
    def is_available_for_current_host(self) -> bool:
        return get_native_host() in self._data


class BlobDecl:
    def __init__(self, data: BlobDeclType) -> None:
        self._data = data

    def get_distfile_names(self) -> list[str] | None:
        return self._data["distfiles"]


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

    def get_binfmt_misc_str(self, install_root: os.PathLike[Any]) -> str | None:
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


class ProvisionableDecl:
    def __init__(self, data: ProvisionableDeclType) -> None:
        self._data = data

    @property
    def partition_map(self) -> PartitionMapDecl:
        return self._data["partition_map"]

    @property
    def strategy(self) -> str:
        return self._data["strategy"]


class PackageMetadataDecl:
    def __init__(self, data: PackageMetadataDeclType) -> None:
        self._data = data


def _translate_to_manifest_v1(obj: InputPackageManifestType) -> PackageManifestType:
    fmt = obj.get("format", "")
    if fmt == "v1":
        return cast(PackageManifestType, obj)
    if fmt != "":
        # unrecognized package format
        raise RuntimeError(f"unrecognized Ruyi package format: {fmt}")

    # translate v0 to v1
    result = deepcopy(obj)
    result["format"] = "v1"

    md: PackageMetadataDeclType = {"desc": "", "vendor": {"name": "", "eula": None}}
    if "slug" in result:
        md["slug"] = result["slug"]
        del result["slug"]
    if "desc" in result:
        md["desc"] = result["desc"]
        del result["desc"]
    if "vendor" in result:
        md["vendor"] = result["vendor"]
        del result["vendor"]
    if "doc_uri" in result:
        md["doc_uri"] = result["doc_uri"]
        del result["doc_uri"]
    result["metadata"] = md

    return cast(PackageManifestType, result)


class PackageManifest:
    def __init__(
        self,
        data: InputPackageManifestType,
    ) -> None:
        self._data = _translate_to_manifest_v1(data)
        if "kind" not in self._data:
            self._data["kind"] = [k for k in ALL_PACKAGE_KINDS if k in self._data]

    @classmethod
    def load_json(cls, stream: BinaryIO) -> Self:
        content = json.load(stream)
        return cls(content)

    @classmethod
    def load_toml(cls, stream: BinaryIO) -> Self:
        content = cast(InputPackageManifestType, tomllib.load(stream))
        return cls(content)

    @classmethod
    def load_from_path(cls, p: pathlib.Path) -> Self:
        suffix = p.suffix.lower()
        match suffix:
            case ".json":
                with open(p, "rb") as fp:
                    return cls.load_json(fp)
            case ".toml":
                with open(p, "rb") as fp:
                    return cls.load_toml(fp)
            case _:
                raise RuntimeError(
                    f"unrecognized package manifest file extension: '{p.suffix}'"
                )

    def to_raw(self) -> PackageManifestType:
        return deepcopy(self._data)

    @property
    def slug(self) -> str | None:
        return self._data["metadata"].get("slug")

    @property
    def kind(self) -> list[PackageKind]:
        return self._data["kind"]

    def has_kind(self, k: PackageKind) -> bool:
        return k in self._data["kind"]

    @property
    def desc(self) -> str:
        return self._data["metadata"]["desc"]

    @property
    def doc_uri(self) -> str | None:
        return self._data["metadata"].get("doc_uri")

    @property
    def vendor_name(self) -> str:
        return self._data["metadata"]["vendor"]["name"]

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
    def blob_metadata(self) -> BlobDecl | None:
        if not self.has_kind("blob"):
            return None
        if "blob" not in self._data:
            return None
        return BlobDecl(self._data["blob"])

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

    @cached_property
    def provisionable_metadata(self) -> ProvisionableDecl | None:
        if not self.has_kind("provisionable"):
            return None
        if "provisionable" not in self._data:
            return None
        return ProvisionableDecl(self._data["provisionable"])


class BoundPackageManifest(PackageManifest):
    def __init__(
        self,
        category: str,
        name: str,
        ver: str,
        data: InputPackageManifestType,
    ) -> None:
        super().__init__(data)

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
    def name_for_installation(self) -> str:
        return f"{self.name}-{self.ver}"


PRERELEASE_TAGS_RE = re.compile(r"^(?:alpha|beta|pre|rc)")


def is_prerelease(sv: Version) -> bool:
    if sv.prerelease is None:
        return False

    # only consider "(alpha|beta|pre|rc).*" versions as prerelease, to accommodate
    # various semver "hacks" as incorporated by upstream(s), and ourselves
    # ("ruyi.YYYYMMDD" are used as ordinary datestamps that affects sorting
    # order, in contrast to build tags).
    # see https://github.com/ruyisdk/ruyi/issues/156
    return PRERELEASE_TAGS_RE.match(sv.prerelease) is not None
