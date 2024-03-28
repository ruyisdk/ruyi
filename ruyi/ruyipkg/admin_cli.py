import argparse
import json
import os
import sys
from typing import Any

from tomlkit import TOMLDocument, document, table
from tomlkit.items import AoT, Table

from .. import log
from . import checksum
from .pkg_manifest import DistfileDeclType


def cli_admin_manifest(args: argparse.Namespace) -> int:
    files = args.file
    format = args.format

    manifest_result = [gen_manifest(f) for f in files]
    if format == "json":
        sys.stdout.write(json.dumps(manifest_result, indent=2))
        sys.stdout.write("\n")
        return 0

    if format == "toml":
        doc = emit_toml_manifest(manifest_result)
        log.D(f"{doc}")
        sys.stdout.write(doc.as_string())
        return 0

    raise RuntimeError("unrecognized output format; should never happen")


def gen_manifest(path: os.PathLike[Any]) -> DistfileDeclType:
    log.D(f"generating manifest for {path}")
    with open(path, "rb") as fp:
        filesize = os.stat(fp.fileno()).st_size
        c = checksum.Checksummer(fp, {})
        checksums = c.compute(kinds=checksum.SUPPORTED_CHECKSUM_KINDS)

    return {
        "name": os.path.basename(path),
        "size": filesize,
        "checksums": checksums,
    }


def emit_toml_manifest(x: list[DistfileDeclType]) -> TOMLDocument:
    doc = document()

    arr: list[Table] = []
    for dd in x:
        t = table()
        t.add("name", dd["name"])
        t.add("size", dd["size"])
        t.add("checksums", emit_toml_checksums(dd["checksums"]))
        arr.append(t)

    doc.add("distfiles", AoT(arr))
    return doc


def emit_toml_checksums(x: dict[str, str]) -> Table:
    t = table()
    for k in sorted(x.keys()):
        t.add(k, x[k])
    return t
