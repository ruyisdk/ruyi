from collections.abc import Generator
from contextlib import contextmanager
import os
import pathlib
import sys

from ruyi.log import RuyiLogger
from ruyi.ruyipkg import unpack
from ruyi.ruyipkg.unpack_method import UnpackMethod, determine_unpack_method

from ..fixtures import RuyiFileFixtureFactory

# -- expected content of the test tree ----------------------------------
BIN_RUNNER = b"#!/bin/sh\necho 'hello from runner'\n"
LIB_HELPER = b"\x7fELF...fake libhelper.so\n"
README = b"= testpkg =\n\nSample package for unpacker tests.\n"
RAW_DATA = b"raw uncompressed data for bare-format testing\n"


@contextmanager
def _unpack_fixture_path(
    ruyi_file: RuyiFileFixtureFactory, name: str
) -> Generator[pathlib.Path, None, None]:
    with ruyi_file.path("ruyipkg_suites", "unpack", name) as p:
        yield p


def _assert_tree(
    base: pathlib.Path,
    *,
    stripped: bool = False,
    check_symlinks: bool = True,
) -> None:
    """Verify the full testpkg-1.0 tree was extracted correctly."""
    pkg = base if stripped else base / "testpkg-1.0"
    assert pkg.is_dir()

    # regular files at various nesting levels
    assert (pkg / "bin" / "runner").read_bytes() == BIN_RUNNER
    assert (pkg / "lib" / "libhelper.so").read_bytes() == LIB_HELPER
    assert (pkg / "share" / "doc" / "README").read_bytes() == README

    if check_symlinks:
        # symlink: lib64 -> lib
        lib64 = pkg / "lib64"
        assert lib64.is_symlink()
        assert os.readlink(str(lib64)) == "lib"


def test_determine_method_tar_gz() -> None:
    assert determine_unpack_method("foo.tar.gz") == UnpackMethod.TAR_GZ


def test_determine_method_tar_bz2() -> None:
    assert determine_unpack_method("foo.tar.bz2") == UnpackMethod.TAR_BZ2


def test_determine_method_tar_lz4() -> None:
    assert determine_unpack_method("foo.tar.lz4") == UnpackMethod.TAR_LZ4


def test_determine_method_tar_xz() -> None:
    assert determine_unpack_method("foo.tar.xz") == UnpackMethod.TAR_XZ


def test_determine_method_tar_zst() -> None:
    assert determine_unpack_method("foo.tar.zst") == UnpackMethod.TAR_ZST


def test_determine_method_tar() -> None:
    assert determine_unpack_method("foo.tar") == UnpackMethod.TAR


def test_determine_method_zip() -> None:
    assert determine_unpack_method("foo.ZIP") == UnpackMethod.ZIP


def test_determine_method_gz() -> None:
    assert determine_unpack_method("foo.gz") == UnpackMethod.GZ


def test_determine_method_bz2() -> None:
    assert determine_unpack_method("foo.BZ2") == UnpackMethod.BZ2


def test_determine_method_lz4() -> None:
    assert determine_unpack_method("foo.lz4") == UnpackMethod.LZ4


def test_determine_method_xz() -> None:
    assert determine_unpack_method("foo.xz") == UnpackMethod.XZ


def test_determine_method_zst() -> None:
    assert determine_unpack_method("foo.zst") == UnpackMethod.ZST


def test_determine_method_unknown() -> None:
    assert determine_unpack_method("README.txt") == UnpackMethod.UNKNOWN


def test_unpack_raw(
    ruyi_file: RuyiFileFixtureFactory,
    ruyi_logger: RuyiLogger,
    tmp_path: pathlib.Path,
) -> None:
    dest = tmp_path / "out"
    dest.mkdir()
    with _unpack_fixture_path(ruyi_file, "rawtest.txt") as src:
        assert determine_unpack_method(str(src)) == UnpackMethod.UNKNOWN
        unpack.do_unpack(ruyi_logger, str(src), str(dest), 0, UnpackMethod.RAW)

    assert (dest / "rawtest.txt").read_bytes() == RAW_DATA


def test_unpack_tar(
    ruyi_file: RuyiFileFixtureFactory,
    ruyi_logger: RuyiLogger,
    tmp_path: pathlib.Path,
) -> None:
    dest = tmp_path / "out"
    dest.mkdir()
    with _unpack_fixture_path(ruyi_file, "testpkg.tar") as src:
        assert determine_unpack_method(str(src)) == UnpackMethod.TAR
        unpack.do_unpack(ruyi_logger, str(src), str(dest), 0, UnpackMethod.TAR)

    _assert_tree(dest)


def test_unpack_tar_strip_components(
    ruyi_file: RuyiFileFixtureFactory,
    ruyi_logger: RuyiLogger,
    tmp_path: pathlib.Path,
) -> None:
    dest = tmp_path / "out"
    dest.mkdir()
    with _unpack_fixture_path(ruyi_file, "testpkg.tar") as src:
        unpack.do_unpack(ruyi_logger, str(src), str(dest), 1, UnpackMethod.TAR)

    _assert_tree(dest, stripped=True)


def test_unpack_tar_gz(
    ruyi_file: RuyiFileFixtureFactory,
    ruyi_logger: RuyiLogger,
    tmp_path: pathlib.Path,
) -> None:
    dest = tmp_path / "out"
    dest.mkdir()
    with _unpack_fixture_path(ruyi_file, "testpkg.tar.gz") as src:
        assert determine_unpack_method(str(src)) == UnpackMethod.TAR_GZ
        unpack.do_unpack(ruyi_logger, str(src), str(dest), 0, UnpackMethod.TAR_GZ)

    _assert_tree(dest)


def test_unpack_tar_bz2(
    ruyi_file: RuyiFileFixtureFactory,
    ruyi_logger: RuyiLogger,
    tmp_path: pathlib.Path,
) -> None:
    dest = tmp_path / "out"
    dest.mkdir()
    with _unpack_fixture_path(ruyi_file, "testpkg.tar.bz2") as src:
        assert determine_unpack_method(str(src)) == UnpackMethod.TAR_BZ2
        unpack.do_unpack(ruyi_logger, str(src), str(dest), 0, UnpackMethod.TAR_BZ2)

    _assert_tree(dest)


def test_unpack_tar_lz4(
    ruyi_file: RuyiFileFixtureFactory,
    ruyi_logger: RuyiLogger,
    tmp_path: pathlib.Path,
) -> None:
    dest = tmp_path / "out"
    dest.mkdir()
    with _unpack_fixture_path(ruyi_file, "testpkg.tar.lz4") as src:
        assert determine_unpack_method(str(src)) == UnpackMethod.TAR_LZ4
        unpack.do_unpack(ruyi_logger, str(src), str(dest), 0, UnpackMethod.TAR_LZ4)

    _assert_tree(dest)


def test_unpack_tar_xz(
    ruyi_file: RuyiFileFixtureFactory,
    ruyi_logger: RuyiLogger,
    tmp_path: pathlib.Path,
) -> None:
    dest = tmp_path / "out"
    dest.mkdir()
    with _unpack_fixture_path(ruyi_file, "testpkg.tar.xz") as src:
        assert determine_unpack_method(str(src)) == UnpackMethod.TAR_XZ
        unpack.do_unpack(ruyi_logger, str(src), str(dest), 0, UnpackMethod.TAR_XZ)

    _assert_tree(dest)


def test_unpack_tar_zst(
    ruyi_file: RuyiFileFixtureFactory,
    ruyi_logger: RuyiLogger,
    tmp_path: pathlib.Path,
) -> None:
    dest = tmp_path / "out"
    dest.mkdir()
    with _unpack_fixture_path(ruyi_file, "testpkg.tar.zst") as src:
        assert determine_unpack_method(str(src)) == UnpackMethod.TAR_ZST
        unpack.do_unpack(ruyi_logger, str(src), str(dest), 0, UnpackMethod.TAR_ZST)

    _assert_tree(dest)


def test_unpack_zip(
    ruyi_file: RuyiFileFixtureFactory,
    ruyi_logger: RuyiLogger,
    tmp_path: pathlib.Path,
) -> None:
    dest = tmp_path / "out"
    dest.mkdir()
    with _unpack_fixture_path(ruyi_file, "testpkg.zip") as src:
        assert determine_unpack_method(str(src)) == UnpackMethod.ZIP
        unpack.do_unpack(ruyi_logger, str(src), str(dest), 0, UnpackMethod.ZIP)

    _assert_tree(dest, check_symlinks=False)  # ZIP files don't support symlinks


def test_unpack_bare_gz(
    ruyi_file: RuyiFileFixtureFactory,
    ruyi_logger: RuyiLogger,
    tmp_path: pathlib.Path,
) -> None:
    dest = tmp_path / "out"
    dest.mkdir()
    with _unpack_fixture_path(ruyi_file, "baretest.txt.gz") as src:
        assert determine_unpack_method(str(src)) == UnpackMethod.GZ
        unpack.do_unpack(ruyi_logger, str(src), str(dest), 0, UnpackMethod.GZ)

    assert (dest / "baretest.txt").read_bytes() == RAW_DATA


def test_unpack_bare_bz2(
    ruyi_file: RuyiFileFixtureFactory,
    ruyi_logger: RuyiLogger,
    tmp_path: pathlib.Path,
) -> None:
    dest = tmp_path / "out"
    dest.mkdir()
    with _unpack_fixture_path(ruyi_file, "baretest.txt.bz2") as src:
        assert determine_unpack_method(str(src)) == UnpackMethod.BZ2
        unpack.do_unpack(ruyi_logger, str(src), str(dest), 0, UnpackMethod.BZ2)

    assert (dest / "baretest.txt").read_bytes() == RAW_DATA


def test_unpack_bare_lz4(
    ruyi_file: RuyiFileFixtureFactory,
    ruyi_logger: RuyiLogger,
    tmp_path: pathlib.Path,
) -> None:
    dest = tmp_path / "out"
    dest.mkdir()
    with _unpack_fixture_path(ruyi_file, "baretest.txt.lz4") as src:
        assert determine_unpack_method(str(src)) == UnpackMethod.LZ4
        unpack.do_unpack(ruyi_logger, str(src), str(dest), 0, UnpackMethod.LZ4)

    assert (dest / "baretest.txt").read_bytes() == RAW_DATA


def test_unpack_bare_xz(
    ruyi_file: RuyiFileFixtureFactory,
    ruyi_logger: RuyiLogger,
    tmp_path: pathlib.Path,
) -> None:
    dest = tmp_path / "out"
    dest.mkdir()
    with _unpack_fixture_path(ruyi_file, "baretest.txt.xz") as src:
        assert determine_unpack_method(str(src)) == UnpackMethod.XZ
        unpack.do_unpack(ruyi_logger, str(src), str(dest), 0, UnpackMethod.XZ)

    assert (dest / "baretest.txt").read_bytes() == RAW_DATA


def test_unpack_bare_zst(
    ruyi_file: RuyiFileFixtureFactory,
    ruyi_logger: RuyiLogger,
    tmp_path: pathlib.Path,
) -> None:
    dest = tmp_path / "out"
    dest.mkdir()
    with _unpack_fixture_path(ruyi_file, "baretest.txt.zst") as src:
        assert determine_unpack_method(str(src)) == UnpackMethod.ZST
        unpack.do_unpack(ruyi_logger, str(src), str(dest), 0, UnpackMethod.ZST)

    assert (dest / "baretest.txt").read_bytes() == RAW_DATA


def test_unpack_or_symlink_unknown_format(
    ruyi_file: RuyiFileFixtureFactory,
    ruyi_logger: RuyiLogger,
    tmp_path: pathlib.Path,
) -> None:
    dest = tmp_path / "out"
    dest.mkdir()
    with _unpack_fixture_path(ruyi_file, "rawtest.txt") as src:
        unpack.do_unpack_or_symlink(
            ruyi_logger,
            str(src),
            str(dest),
            0,
            UnpackMethod.UNKNOWN,
        )

    link = dest / "rawtest.txt"
    assert link.is_symlink()
    assert os.readlink(str(link)) == os.path.abspath(str(src))
    assert link.read_bytes() == RAW_DATA


def test_unpack_deb(
    ruyi_file: RuyiFileFixtureFactory,
    ruyi_logger: RuyiLogger,
    tmp_path: pathlib.Path,
) -> None:
    with ruyi_file.path("cpp-for-host_14-20240120-6_riscv64.deb") as p:
        assert determine_unpack_method(str(p)) == UnpackMethod.DEB
        unpack.do_unpack(
            ruyi_logger,
            str(p),
            str(tmp_path),
            0,
            UnpackMethod.DEB,
            None,
        )
        check = tmp_path / "usr" / "share" / "doc" / "cpp-for-host"
        if sys.version_info >= (3, 12):
            assert check.exists(follow_symlinks=False)
        else:
            # Python 3.11 lacks pathlib.Path.exists(follow_symlinks)
            #
            # we know that this path is going to be a symlink so simply
            # ensuring it's existent is enough; asserting that it is dangling
            # risks breaking CI on systems where the target actually exists
            assert check.lstat() is not None
        assert check.is_symlink()
        assert str(check.readlink()) == "cpp-riscv64-linux-gnu"
