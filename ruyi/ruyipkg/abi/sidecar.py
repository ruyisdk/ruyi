"""Scan a path (archive or directory) into a written ``.abi.toml`` sidecar.

Shared by ``ruyi admin rescan-package-abi`` and the ``build-package``
executor. Heavy imports stay inside functions to keep CLI startup light.
"""

from __future__ import annotations

import pathlib
from typing import TYPE_CHECKING, Sequence

from ..unpack_method import UnpackMethod, determine_unpack_method

if TYPE_CHECKING:
    from ...log import RuyiLogger
    from .model import ABIReport
    from .sources import ABISource

SIDECAR_SUFFIX = ".abi.toml"

_SCANNABLE_ARCHIVE_METHODS = frozenset(
    {
        UnpackMethod.TAR,
        UnpackMethod.TAR_GZ,
        UnpackMethod.TAR_BZ2,
        UnpackMethod.TAR_LZ4,
        UnpackMethod.TAR_XZ,
        UnpackMethod.TAR_ZST,
        UnpackMethod.ZIP,
        UnpackMethod.DEB,
    }
)


def sidecar_path_for(target: pathlib.Path) -> pathlib.Path:
    return target.with_name(target.name + SIDECAR_SUFFIX)


def is_scannable(target: pathlib.Path) -> bool:
    if target.is_dir():
        return True
    return determine_unpack_method(target.name) in _SCANNABLE_ARCHIVE_METHODS


def make_source(target: pathlib.Path) -> "ABISource":
    from .sources import ABISource

    if target.is_dir():
        return ABISource.from_directory(target)
    return ABISource.from_archive(target)


def scan_path(
    logger: "RuyiLogger",
    target: pathlib.Path,
    *,
    exclude: Sequence[str] = (),
) -> "ABIReport":
    from . import scan_source

    return scan_source(make_source(target), logger=logger, exclude=exclude)


def write_sidecar(report: "ABIReport", path: pathlib.Path) -> None:
    import os
    import tempfile

    from . import dump_abi_report_toml

    text = dump_abi_report_toml(report)
    fd, tmp = tempfile.mkstemp(
        prefix=f"{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fp:
            fp.write(text)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
