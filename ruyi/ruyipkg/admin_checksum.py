import os
import sys
from pathlib import Path
from typing import Any, TypeGuard

from tomlkit import document, table
from tomlkit.items import AoT, Table
from tomlkit.toml_document import TOMLDocument

from ..i18n import _
from ..log import RuyiLogger
from . import checksum
from .install_size import compute_install_size
from .pkg_manifest import DistfileDeclType, RestrictKind
from .unpack_method import determine_unpack_method


def do_admin_checksum(
    logger: RuyiLogger,
    files: list[os.PathLike[Any]],
    format: str,
    restrict: list[str],
    *,
    install_size: bool = False,
) -> int:
    if not validate_restrict_kinds(restrict):
        logger.F(
            _("invalid restrict kinds given: {restrict}").format(restrict=restrict)
        )
        return 1

    entries = [gen_distfile_entry(logger, f, restrict) for f in files]
    if format == "toml":
        doc = emit_toml_distfiles_section(entries)
        logger.D(f"{doc}")
        sys.stdout.write(doc.as_string())

        if install_size:
            _emit_install_size_comment(logger, files)

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


def _emit_install_size_comment(
    logger: RuyiLogger,
    files: list[os.PathLike[Any]],
) -> None:
    total = 0
    sizes: list[tuple[str, int]] = []

    for f in files:
        path = Path(os.fspath(f))
        name = path.name
        try:
            method = determine_unpack_method(name)
            size = compute_install_size(path, method)
        except Exception as exc:
            logger.W(
                _("cannot compute install size for {name}: {error}").format(
                    name=name,
                    error=exc,
                )
            )
            continue

        sizes.append((name, size))
        total += size

    if not sizes:
        return

    lines = [
        "",
        "# --- install_size (generated with --install-size) ---",
        "# Paste into the appropriate section metadata:",
        "#   [<kind>.metadata]",
        f"#   install_size = {total}",
    ]
    sys.stdout.write("\n".join(lines) + "\n")
