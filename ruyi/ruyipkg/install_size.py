"""Compute install size metadata for distfile artifacts."""

import io
import mmap
import os
from pathlib import Path

from .unpack import open_decompressed
from .unpack_method import UnpackMethod


def compute_install_size(path: Path, unpack_method: UnpackMethod) -> int:
    """Return the sum of member file sizes for an archive at `path`.

    For tar/zip/deb/raw formats this inspects archive metadata without
    extracting to disk.  Compressed single-file streams are decompressed
    to a temporary file to measure.

    Raises ValueError for unrecognized unpack methods.
    """

    match unpack_method:
        case (
            UnpackMethod.TAR
            | UnpackMethod.TAR_AUTO
            | UnpackMethod.TAR_GZ
            | UnpackMethod.TAR_BZ2
            | UnpackMethod.TAR_LZ4
            | UnpackMethod.TAR_XZ
            | UnpackMethod.TAR_ZST
        ):
            return _install_size_tar(str(path))

        case UnpackMethod.ZIP:
            return _install_size_zip(str(path))

        case UnpackMethod.DEB:
            return _install_size_deb(str(path))

        case UnpackMethod.RAW:
            return os.stat(path).st_size

        case (
            UnpackMethod.GZ
            | UnpackMethod.BZ2
            | UnpackMethod.XZ
            | UnpackMethod.LZ4
            | UnpackMethod.ZST
        ):
            return _install_size_decompressed_stream(str(path), unpack_method)

        case _:
            raise ValueError(
                f"unsupported unpack method for install size: {unpack_method}"
            )


def _install_size_tar(path: str) -> int:
    import tarfile

    total = 0
    with tarfile.open(path, mode="r:*") as tf:
        for member in tf.getmembers():
            if member.isreg():
                total += member.size
    return total


def _install_size_zip(path: str) -> int:
    import zipfile

    total = 0
    with zipfile.ZipFile(path) as zf:
        for info in zf.infolist():
            total += info.file_size
    return total


def _install_size_deb(path: str) -> int:
    import tarfile

    import arpy

    ar = arpy.Archive(path)
    for entry in ar:
        if entry.header.name.startswith(b"data.tar"):
            data = entry.read()
            total = 0
            with tarfile.open(fileobj=io.BytesIO(data), mode="r:*") as tf:
                for member in tf.getmembers():
                    if member.isreg():
                        total += member.size
            return total
    raise RuntimeError(f"no data.tar found in deb package: {path}")


def _install_size_decompressed_stream(
    path: str,
    unpack_method: UnpackMethod,
) -> int:
    """Decompress a single-file compressed stream to measure its unpacked size."""
    size = 0
    bufsize = 4 * mmap.PAGESIZE
    with open_decompressed(path, unpack_method) as f:
        while True:
            chunk = f.read(bufsize)
            if not chunk:
                break
            size += len(chunk)
    return size
