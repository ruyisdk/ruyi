import argparse
import json
import os
import pathlib
import sys
from typing import Any, TypeGuard, cast

from tomlkit import TOMLDocument, document, table
from tomlkit.items import AoT, Table

from .. import log
from . import checksum
from .canonical_dump import dump_canonical_package_manifest_toml
from .pkg_manifest import DistfileDeclType, PackageManifest, RestrictKind


def cli_admin_manifest(args: argparse.Namespace) -> int:
    files = args.file
    format = args.format
    restrict_str = cast(str, args.restrict)
    restrict = restrict_str.split(",") if restrict_str else []

    if not validate_restrict_kinds(restrict):
        log.F(f"invalid restrict kinds given: {restrict}")
        return 1

    entries = [gen_distfile_entry(f, restrict) for f in files]
    if format == "json":
        sys.stdout.write(json.dumps(entries, indent=2))
        sys.stdout.write("\n")
        return 0

    if format == "toml":
        doc = emit_toml_distfiles_section(entries)
        log.D(f"{doc}")
        sys.stdout.write(doc.as_string())
        return 0

    raise RuntimeError("unrecognized output format; should never happen")


def cli_admin_format_manifest(args: argparse.Namespace) -> int:
    files = args.file

    for f in files:
        p = pathlib.Path(f)
        pm = PackageManifest.load_from_path(p)
        d = dump_canonical_package_manifest_toml(pm.to_raw())

        dest_path = p.with_suffix(".toml")
        with open(dest_path, "w") as fp:
            # XXX: To workaround https://github.com/python-poetry/tomlkit/issues/290,
            # post-process the output to have all leading 4-space indentation
            # before a string literal replaced by 2-space ones.
            fp.write(d.as_string().replace('\n    "', '\n  "'))

    return 0


def validate_restrict_kinds(input: list[str]) -> TypeGuard[list[RestrictKind]]:
    for x in input:
        match x:
            case "fetch" | "mirror":
                pass
            case _:
                return False
    return True


def gen_distfile_entry(
    path: os.PathLike[Any],
    restrict: list[RestrictKind],
) -> DistfileDeclType:
    log.D(f"generating distfile entry for {path}")
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
