from typing import Iterable, NotRequired, TypedDict


class VendorDeclType(TypedDict):
    name: str
    eula: str | None


class DistfileDeclType(TypedDict):
    name: str
    size: int
    checksums: dict[str, str]


class BinaryFileDeclType(TypedDict):
    host: str
    distfiles: list[str]


BinaryDeclType = list[BinaryFileDeclType]


class ToolchainComponentDeclType(TypedDict):
    name: str
    version: str


class ToolchainDeclType(TypedDict):
    target: str
    flavors: list[str]
    components: list[ToolchainComponentDeclType]


class PackageManifestType(TypedDict):
    slug: str
    kind: list[str]
    name: str
    vendor: VendorDeclType
    distfiles: list[DistfileDeclType]
    binary: NotRequired[BinaryDeclType]
    toolchain: NotRequired[ToolchainDeclType]
