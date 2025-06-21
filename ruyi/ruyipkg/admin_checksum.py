import os
import sys
from typing import Any, TypeGuard

from tomlkit import document, table
from tomlkit.items import AoT, Table
from tomlkit.toml_document import TOMLDocument

from ..log import RuyiLogger
from . import checksum
from .pkg_manifest import DistfileDeclType, RestrictKind


def do_admin_checksum(
    logger: RuyiLogger,
    files: list[os.PathLike[Any]],
    format: str,
    restrict: list[str],
) -> int:
    if not validate_restrict_kinds(restrict):
        logger.F(f"invalid restrict kinds given: {restrict}")
        return 1

    entries = [gen_distfile_entry(logger, f, restrict) for f in files]
    if format == "toml":
        doc = emit_toml_distfiles_section(entries)
        logger.D(f"{doc}")
        sys.stdout.write(doc.as_string())
        return 0

    raise RuntimeError("unrecognized output format; should never happen")


def validate_restrict_kinds(input: list[str]) -> TypeGuard[list[RestrictKind]]:
    for x in input:
        match x:
            case "fetch" | "mirror":
                pass
            case _:
                return False
    return True


def gen_distfile_entry(
    logger: RuyiLogger,
    path: os.PathLike[Any],
    restrict: list[RestrictKind],
) -> DistfileDeclType:
    logger.D(f"generating distfile entry for {path}")
    with open(path, "rb") as fp:
        filesize = os.stat(fp.fileno()).st_size
        c = checksum.Checksummer(fp, {})
        checksums = c.compute(kinds=checksum.SUPPORTED_CHECKSUM_KINDS)

    obj: DistfileDeclType = {
        "name": os.path.basename(path),
        "size": filesize,
        "checksums": checksums,
    }

    if restrict:
        obj["restrict"] = restrict

    return obj


def emit_toml_distfiles_section(x: list[DistfileDeclType]) -> TOMLDocument:
    doc = document()

    arr: list[Table] = []
    for dd in x:
        t = table()
        t.add("name", dd["name"])
        t.add("size", dd["size"])
        if r := dd.get("restrict"):
            t.add("restrict", r)
        t.add("checksums", emit_toml_checksums(dd["checksums"]))
        arr.append(t)

    doc.add("distfiles", AoT(arr))
    return doc


def emit_toml_checksums(x: dict[str, str]) -> Table:
    t = table()
    for k in sorted(x.keys()):
        t.add(k, x[k])
    return t
