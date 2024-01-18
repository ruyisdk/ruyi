import argparse
import json
import os
import sys
from typing import Any

from .. import log

from . import checksum
from .pkg_manifest import DistfileDeclType


def cli_admin_manifest(args: argparse.Namespace) -> int:
    files = args.file

    manifest_result = [gen_manifest(f) for f in files]
    manifest_json = json.dumps(manifest_result, indent=2)
    sys.stdout.write(manifest_json)
    sys.stdout.write("\n")

    return 0


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
