import argparse
import os
import pathlib
import sys
from typing import Any, TypeGuard, cast

from tomlkit import document, table
from tomlkit.items import AoT, Table
from tomlkit.toml_document import TOMLDocument

from ..cli.cmd import AdminCommand
from ..config import GlobalConfig
from ..log import RuyiLogger
from . import checksum
from .canonical_dump import dumps_canonical_package_manifest_toml
from .pkg_manifest import DistfileDeclType, PackageManifest, RestrictKind


class AdminChecksumCommand(
    AdminCommand,
    cmd="checksum",
    help="Generate a checksum section for a manifest file for the distfiles given",
):
    @classmethod
    def configure_args(cls, gc: GlobalConfig, p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "--format",
            "-f",
            type=str,
            choices=["toml"],
            default="toml",
            help="Format of checksum section to generate in",
        )
        p.add_argument(
            "--restrict",
            type=str,
            default="",
            help="the 'restrict' field to use for all mentioned distfiles, separated with comma",
        )
        p.add_argument(
            "file",
            type=str,
            nargs="+",
            help="Path to the distfile(s) to checksum",
        )

    @classmethod
    def main(cls, cfg: GlobalConfig, args: argparse.Namespace) -> int:
        logger = cfg.logger
        files = args.file
        format = args.format
        restrict_str = cast(str, args.restrict)
        restrict = restrict_str.split(",") if restrict_str else []

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


class AdminFormatManifestCommand(
    AdminCommand,
    cmd="format-manifest",
    help="Format the given package manifests into canonical TOML representation",
):
    @classmethod
    def configure_args(cls, gc: GlobalConfig, p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "file",
            type=str,
            nargs="+",
            help="Path to the distfile(s) to generate manifest for",
        )

    @classmethod
    def main(cls, cfg: GlobalConfig, args: argparse.Namespace) -> int:
        files = args.file

        for f in files:
            p = pathlib.Path(f)
            pm = PackageManifest.load_from_path(p)
            d = dumps_canonical_package_manifest_toml(pm)

            dest_path = p.with_suffix(".toml")
            with open(dest_path, "w", encoding="utf-8") as fp:
                fp.write(d)

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
