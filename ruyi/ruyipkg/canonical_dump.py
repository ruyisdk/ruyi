from tomlkit import TOMLDocument
from tomlkit import document, nl, string, table
from tomlkit.items import AoT, InlineTable, Table

from .pkg_manifest import (
    BlobDeclType,
    DistfileDeclType,
    FetchRestrictionDeclType,
    PackageManifestType,
    PackageMetadataDeclType,
    ProvisionableDeclType,
    VendorDeclType,
)
from ..utils.toml import inline_table_with_spaces, sorted_table, str_array


def dump_canonical_package_manifest_toml(
    x: PackageManifestType,
) -> TOMLDocument:
    y = document()

    y.add("format", string(x["format"]))

    dump_metadata_decl_into(y, x["metadata"])
    dump_distfile_decls_into(y, x["distfiles"])
    maybe_dump_blob_decl_into(y, x.get("blob"))
    maybe_dump_provisionable_decl_into(y, x.get("provisionable"))

    return y


def dump_metadata_decl(x: PackageMetadataDeclType) -> Table:
    y = table()
    y.add("desc", string(x["desc"]))
    y.add("vendor", dump_vendor_decl(x["vendor"]))
    if "slug" in x:
        y.add("slug", string(x["slug"]))
    return y


def dump_metadata_decl_into(doc: TOMLDocument, x: PackageMetadataDeclType) -> None:
    doc.add(nl())
    doc.add("metadata", dump_metadata_decl(x))


def dump_vendor_decl(x: VendorDeclType) -> InlineTable:
    y = inline_table_with_spaces()
    with y:
        y.add("name", string(x["name"]))
        y.add("eula", string(x["eula"] if x["eula"] is not None else ""))
    return y


def dump_distfile_decls(x: list[DistfileDeclType]) -> AoT:
    return AoT([dump_distfile_entry(i) for i in x])


def dump_distfile_decls_into(doc: TOMLDocument, x: list[DistfileDeclType]) -> None:
    doc.add(nl())
    doc.add("distfiles", dump_distfile_decls(x))


def dump_distfile_entry(x: DistfileDeclType) -> Table:
    y = table()
    y.add("name", x["name"])
    if v := x.get("unpack"):
        y.add("unpack", string(v))
    y.add("size", x["size"])
    if s := x.get("strip_components"):
        if s != 1:
            y.add("strip_components", s)
    if "urls" in x:
        # XXX: https://github.com/python-poetry/tomlkit/issues/290 prevents us
        # from using 2-space indentation for the array items for now.
        y.add("urls", str_array(x["urls"], multiline=True))
    if r := x.get("restrict"):
        y.add("restrict", r)
    if f := x.get("fetch_restriction"):
        y.add("fetch_restriction", dump_fetch_restriction(f))
    y.add("checksums", sorted_table(x["checksums"]))
    return y


def dump_fetch_restriction(x: FetchRestrictionDeclType) -> Table:
    y = table()
    y.add("msgid", x["msgid"])
    if "params" in x:
        y.add("params", sorted_table(x["params"]))
    return y


def dump_blob_decl(x: BlobDeclType) -> Table:
    y = table()
    y.add("distfiles", str_array(x["distfiles"], multiline=True))
    return y


def maybe_dump_blob_decl_into(doc: TOMLDocument, x: BlobDeclType | None) -> None:
    if x is None:
        return
    doc.add(nl())
    doc.add("blob", dump_blob_decl(x))


def dump_provisionable_decl(x: ProvisionableDeclType) -> Table:
    y = table()
    y.add("strategy", x["strategy"])
    y.add(
        "partition_map",
        sorted_table({str(k): v for k, v in x["partition_map"].items()}),
    )
    return y


def maybe_dump_provisionable_decl_into(
    doc: TOMLDocument,
    x: ProvisionableDeclType | None,
) -> None:
    if x is None:
        return
    doc.add(nl())
    doc.add("provisionable", dump_provisionable_decl(x))
