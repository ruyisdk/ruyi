from copy import deepcopy
import re
from typing import Final

from tomlkit import comment, document, nl, string, table, ws
from tomlkit.items import AoT, Array, InlineTable, Table, Trivia
from tomlkit.toml_document import TOMLDocument

from .pkg_manifest import (
    BinaryDeclType,
    BinaryFileDeclType,
    BlobDeclType,
    DistfileDeclType,
    EmulatorDeclType,
    EmulatorProgramDeclType,
    FetchRestrictionDeclType,
    PackageManifest,
    PackageMetadataDeclType,
    ProvisionableDeclType,
    ServiceLevelDeclType,
    SourceDeclType,
    ToolchainComponentDeclType,
    ToolchainDeclType,
    VendorDeclType,
)
from ..utils.toml import (
    extract_footer_comments,
    extract_header_comments,
    inline_table_with_spaces,
    sorted_table,
    str_array,
)

RE_INDENT_FIX: Final = re.compile(r"(?m)^    ([\"'{\[])")


# XXX: To workaround https://github.com/python-poetry/tomlkit/issues/290,
# post-process the output to have all leading 4-space indentation before
# strings, lists or tables replaced by 2-space ones.
def _fix_indent(s: str) -> str:
    return RE_INDENT_FIX.sub(r"  \1", s)


def dumps_canonical_package_manifest_toml(
    pm: PackageManifest,
) -> str:
    return _fix_indent(_dump_canonical_package_manifest_toml(pm).as_string())


def _dump_canonical_package_manifest_toml(
    pm: PackageManifest,
) -> TOMLDocument:
    x = pm.to_raw()
    doc = pm.raw_doc

    y = document()

    if doc is not None:
        if header_comments := extract_header_comments(doc):
            last_is_ws = False
            for c in header_comments:
                if c.startswith("#"):
                    last_is_ws = False
                    y.add(comment(c[1:].strip()))
                else:
                    last_is_ws = True
                    y.add(ws(c))

            if not last_is_ws:
                y.add(nl())

    y.add("format", string(x["format"]))

    dump_metadata_decl_into(y, x["metadata"])
    dump_distfile_decls_into(y, x["distfiles"])
    maybe_dump_binary_decls_into(y, x.get("binary"))
    maybe_dump_blob_decl_into(y, x.get("blob"))
    maybe_dump_emulator_decl_into(y, x.get("emulator"))
    maybe_dump_provisionable_decl_into(y, x.get("provisionable"))
    maybe_dump_source_decl_into(y, x.get("source"))
    maybe_dump_toolchain_decl_into(y, x.get("toolchain"))

    if doc is not None:
        if footer_comments := extract_footer_comments(doc):
            if footer_comments[0].startswith("#"):
                y.add(nl())

            for c in footer_comments:
                if c.startswith("#"):
                    y.add(comment(c[1:].strip()))
                else:
                    y.add(ws(c))

    return y


def dump_service_level_entry(x: ServiceLevelDeclType) -> Table:
    y = table()
    y.add("level", x["level"])
    if msgid := x.get("msgid"):
        y.add("msgid", string(msgid))
    if params := x.get("params"):
        y.add("params", sorted_table(params))
    return y


def dump_service_level_decls(x: list[ServiceLevelDeclType]) -> AoT:
    return AoT([dump_service_level_entry(i) for i in x])


def dump_metadata_decl(x: PackageMetadataDeclType) -> Table:
    y = table()
    y.add("desc", string(x["desc"]))
    y.add("vendor", dump_vendor_decl(x["vendor"]))
    if "slug" in x:
        y.add("slug", string(x["slug"]))
    if uv := x.get("upstream_version"):
        y.add("upstream_version", string(uv))
    if sl := x.get("service_level"):
        y.add(nl())
        y.add("service_level", dump_service_level_decls(sl))
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
    if p := x.get("prefixes_to_unpack"):
        y.add("prefixes_to_unpack", str_array(p, multiline=len(p) > 1))
    if "urls" in x:
        # XXX: https://github.com/python-poetry/tomlkit/issues/290 prevents us
        # from using 2-space indentation for the array items for now.
        y.add("urls", str_array([str(i) for i in x["urls"]], multiline=True))
    if r := x.get("restrict"):
        # If `restrict` is a string, convert it to a list, fixing a common
        # oversight in package manifests.
        if isinstance(r, str):
            r = [r]
        y.add("restrict", [str(i) for i in r])
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


def dump_binary_decl(x: BinaryFileDeclType, last: bool) -> Table:
    y = table()
    y.add("host", string(x["host"]))
    multiline_distfiles = len(x["distfiles"]) > 1
    y.add("distfiles", str_array(x["distfiles"], multiline=multiline_distfiles))
    if cmds := x.get("commands", {}):
        y.add("commands", sorted_table(cmds))
        if not last:
            y.add(nl())
    return y


def dump_binary_decls(x: list[BinaryFileDeclType]) -> AoT:
    return AoT([dump_binary_decl(elem, i == len(x) - 1) for i, elem in enumerate(x)])


def maybe_dump_binary_decls_into(doc: TOMLDocument, x: BinaryDeclType | None) -> None:
    if x is None:
        return
    doc.add("binary", dump_binary_decls(x))


def dump_emulator_program_decl(x: EmulatorProgramDeclType) -> Table:
    y = table()
    y.add("path", string(x["path"]))
    y.add("flavor", string(x["flavor"]))
    y.add("supported_arches", str_array(x["supported_arches"]))
    if "binfmt_misc" in x:
        y.add("binfmt_misc", string(x["binfmt_misc"]))
    return y


def dump_emulator_decl(x: EmulatorDeclType) -> Table:
    y = table()
    # Prefer `quirks` to `flavors`
    quirks = x.get("quirks")
    if quirks is None:
        quirks = x.get("flavors", [])
    y.add("quirks", str_array(quirks))
    y.add("programs", AoT([dump_emulator_program_decl(i) for i in x["programs"]]))
    return y


def maybe_dump_emulator_decl_into(
    doc: TOMLDocument, x: EmulatorDeclType | None
) -> None:
    if x is None:
        return
    doc.add(nl())
    doc.add("emulator", dump_emulator_decl(x))


def dump_source_decl(x: SourceDeclType) -> Table:
    y = table()
    multiline_distfiles = len(x["distfiles"]) > 1
    y.add("distfiles", str_array(x["distfiles"], multiline=multiline_distfiles))
    return y


def maybe_dump_source_decl_into(doc: TOMLDocument, x: SourceDeclType | None) -> None:
    if x is None:
        return
    doc.add(nl())
    doc.add("source", dump_source_decl(x))


def dump_toolchain_component_decl(x: ToolchainComponentDeclType) -> InlineTable:
    y = inline_table_with_spaces()
    with y:
        y.add("name", string(x["name"]))
        y.add("version", string(x["version"]))
    return y


def dump_toolchain_component_decls(x: list[ToolchainComponentDeclType]) -> Array:
    sorted_x = deepcopy(x)
    sorted_x.sort(key=lambda i: i["name"])
    return Array(
        [dump_toolchain_component_decl(i) for i in sorted_x],
        Trivia(),
        multiline=True,
    )


def dump_toolchain_decl(x: ToolchainDeclType) -> Table:
    y = table()
    y.add("target", string(x["target"]))
    # Prefer `quirks` to `flavors`
    quirks = x.get("quirks")
    if quirks is None:
        quirks = x.get("flavors", [])
    y.add("quirks", str_array(quirks))
    y.add("components", dump_toolchain_component_decls(x["components"]))
    if "included_sysroot" in x:
        y.add("included_sysroot", x["included_sysroot"])
    return y


def maybe_dump_toolchain_decl_into(
    doc: TOMLDocument,
    x: ToolchainDeclType | None,
) -> None:
    if x is None:
        return
    doc.add(nl())
    doc.add("toolchain", dump_toolchain_decl(x))
