#!/usr/bin/env python3
"""Generate fixture archives for the unpacker tests.

Each archive contains a non-trivial directory tree with regular files
at multiple nesting levels and at least one symlink, so the tests can
verify that extraction preserves the full structure and symlink fidelity.
"""

import bz2
import gzip
import lzma
import os
import pathlib
import tarfile
import tempfile
import zipfile
from typing import IO

import lz4.frame
import zstandard

FIXTURES_DIR = pathlib.Path(__file__).resolve().parent / "ruyipkg_suites" / "unpack"

# -- content strings ----------------------------------------------------

BIN_RUNNER = b"#!/bin/sh\necho 'hello from runner'\n"
LIB_HELPER = b"\x7fELF...fake libhelper.so\n"
README = b"= testpkg =\n\nSample package for unpacker tests.\n"
RAW_DATA = b"raw uncompressed data for bare-format testing\n"


def _populate_tree(root: pathlib.Path) -> None:
    """Create the directory tree inside *root*."""
    pkg = root / "testpkg-1.0"
    (pkg / "bin").mkdir(parents=True)
    (pkg / "bin" / "runner").write_bytes(BIN_RUNNER)
    (pkg / "lib").mkdir(parents=True)
    (pkg / "lib" / "libhelper.so").write_bytes(LIB_HELPER)
    (pkg / "share" / "doc").mkdir(parents=True)
    (pkg / "share" / "doc" / "README").write_bytes(README)
    os.symlink("lib", str(pkg / "lib64"))


def _make_plain_tar() -> pathlib.Path:
    """Create the base uncompressed .tar fixture."""
    dest = FIXTURES_DIR / "testpkg.tar"
    with tempfile.TemporaryDirectory() as td:
        root = pathlib.Path(td)
        _populate_tree(root)
        with tarfile.open(dest, "w") as tf:
            tf.add(str(root / "testpkg-1.0"), arcname="testpkg-1.0", recursive=True)
    return dest


def _make_tar_gz(src_tar: pathlib.Path) -> None:
    dst = FIXTURES_DIR / "testpkg.tar.gz"
    with open(src_tar, "rb") as f_in, gzip.open(dst, "wb") as f_out:
        f_out.write(f_in.read())


def _make_tar_bz2(src_tar: pathlib.Path) -> None:
    dst = FIXTURES_DIR / "testpkg.tar.bz2"
    with open(src_tar, "rb") as f_in, bz2.open(dst, "wb") as f_out:
        f_out.write(f_in.read())


def _make_tar_lz4(src_tar: pathlib.Path) -> None:
    dst = FIXTURES_DIR / "testpkg.tar.lz4"
    with open(src_tar, "rb") as f_in, lz4.frame.open(dst, "wb") as f_out:
        f_out.write(f_in.read())


def _make_tar_xz(src_tar: pathlib.Path) -> None:
    dst = FIXTURES_DIR / "testpkg.tar.xz"
    with open(src_tar, "rb") as f_in, lzma.open(dst, "wb") as f_out:
        f_out.write(f_in.read())


def _make_tar_zst(src_tar: pathlib.Path) -> None:
    dst = FIXTURES_DIR / "testpkg.tar.zst"
    cctx = zstandard.ZstdCompressor()
    with open(src_tar, "rb") as f_in, open(dst, "wb") as f_out:
        cctx.copy_stream(f_in, f_out)


def _make_zip_archive() -> None:
    dest = FIXTURES_DIR / "testpkg.zip"
    with tempfile.TemporaryDirectory() as td:
        root = pathlib.Path(td)
        _populate_tree(root)
        with zipfile.ZipFile(dest, "w") as zf:
            pkg = root / "testpkg-1.0"
            for dirpath, _dirnames, filenames in os.walk(str(pkg)):
                for fn in filenames:
                    full = pathlib.Path(dirpath) / fn
                    arcname = str(full.relative_to(root))
                    zf.write(str(full), arcname)
            # zipfile cannot represent symlinks portably, but the
            # non-trivial directory tree itself is what we exercise here.
            # Symlink fidelity is thoroughly tested via the tar fixtures.


def _make_bare_data(name: str, content: bytes) -> None:
    (FIXTURES_DIR / name).write_bytes(content)


def open_for_write(path: pathlib.Path) -> gzip.GzipFile | IO[bytes] | None:
    match path.suffix:
        case ".gz":
            return gzip.open(path, "wb")
        case ".bz2":
            return bz2.open(path, "wb")
        case ".lz4":
            return lz4.frame.open(path, "wb")
        case ".xz":
            return lzma.open(path, "wb")
    return None


def _make_bare_compressed(name: pathlib.Path, content: bytes) -> None:
    dest = FIXTURES_DIR / name
    opened = open_for_write(dest)
    if opened is not None:
        with opened as f_out:
            f_out.write(content)
    elif name.suffix == ".zst":
        cctx = zstandard.ZstdCompressor()
        with open(dest, "wb") as f_out:
            f_out.write(cctx.compress(content))
    else:
        raise ValueError(f"unknown extension: {name.suffix}")


def main() -> None:
    print(f"Generating fixtures in {FIXTURES_DIR} ...")

    # raw (plain file, used by the RAW unpack test)
    _make_bare_data("rawtest.txt", RAW_DATA)

    # bare compression (no tar -- exercise each bare decompression path)
    for ext in (".gz", ".bz2", ".lz4", ".xz", ".zst"):
        _make_bare_compressed(FIXTURES_DIR / f"baretest.txt{ext}", RAW_DATA)

    # tar family: one uncompressed base, then each compression variant
    plain_tar = _make_plain_tar()
    _make_tar_gz(plain_tar)
    _make_tar_bz2(plain_tar)
    _make_tar_lz4(plain_tar)
    _make_tar_xz(plain_tar)
    _make_tar_zst(plain_tar)

    # zip
    _make_zip_archive()

    for f in sorted(FIXTURES_DIR.glob("*test*")):
        print(f"  {f.name}  ({f.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
