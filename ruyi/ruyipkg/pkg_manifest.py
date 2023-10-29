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


class BinaryDecl:
    def __init__(self, data: BinaryDeclType) -> None:
        self._data = {d["host"]: d["distfiles"] for d in data}

    @property
    def data(self) -> dict[str, list[str]]:
        return self._data

    def get_distfile_names_for_host(self, host: str) -> list[str] | None:
        return self._data.get(host)


class ToolchainDecl:
    def __init__(self, data: ToolchainDeclType) -> None:
        self._data = data

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


class PackageManifest:
    def __init__(self, data: PackageManifestType) -> None:
        self._data = data

    @property
    def slug(self) -> str:
        return self._data["slug"]

    @property
    def kind(self) -> list[str]:
        return self._data["kind"]

    def has_kind(self, k: str) -> bool:
        return k in self._data["kind"]

    @property
    def name(self) -> str:
        return self._data["name"]

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
    def toolchain_metadata(self) -> ToolchainDecl | None:
        if not self.has_kind("toolchain"):
            return None
        if "toolchain" not in self._data:
            return None
        return ToolchainDecl(self._data["toolchain"])
