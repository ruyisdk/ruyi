import pathlib
import tarfile
import zipfile

from ruyi.ruyipkg.abi.sources import ABISource
from ruyi.ruyipkg.unpack_method import UnpackMethod
from tests.ruyipkg.abi._elfbuilder import build_elf


def test_directory_source(tmp_path: pathlib.Path) -> None:
    (tmp_path / "a.bin").write_bytes(b"AAA")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "b.bin").write_bytes(b"BBBB")

    src = ABISource.from_directory(tmp_path)
    members = {path: reader() for path, _size, reader in src.iter_members()}
    assert members == {"a.bin": b"AAA", "sub/b.bin": b"BBBB"}


def test_directory_skips_symlinks(tmp_path: pathlib.Path) -> None:
    (tmp_path / "real.bin").write_bytes(b"R")
    (tmp_path / "link.bin").symlink_to(tmp_path / "real.bin")
    src = ABISource.from_directory(tmp_path)
    paths = [p for p, _s, _r in src.iter_members()]
    assert paths == ["real.bin"]


def test_tar_gz_source(tmp_path: pathlib.Path) -> None:
    (tmp_path / "x.bin").write_bytes(b"hello")
    arc = tmp_path / "a.tar.gz"
    with tarfile.open(arc, "w:gz") as tf:
        tf.add(tmp_path / "x.bin", arcname="x.bin")
    src = ABISource.from_archive(arc, UnpackMethod.TAR_GZ)
    members = {p: r() for p, _s, r in src.iter_members()}
    assert members["x.bin"] == b"hello"


def test_zip_source(tmp_path: pathlib.Path) -> None:
    arc = tmp_path / "a.zip"
    with zipfile.ZipFile(arc, "w") as zf:
        zf.writestr("y.bin", b"world!")
    src = ABISource.from_archive(arc, UnpackMethod.ZIP)
    members = {p: r() for p, _s, r in src.iter_members()}
    assert members["y.bin"] == b"world!"


def _make_tar(tmp_path: pathlib.Path) -> pathlib.Path:
    payload = build_elf(e_machine=243)
    (tmp_path / "x").write_bytes(payload)
    raw = tmp_path / "a.tar"
    with tarfile.open(raw, "w") as tf:
        tf.add(tmp_path / "x", arcname="x")
    return raw


def test_tar_zst_source_streams_members(tmp_path: pathlib.Path) -> None:
    import zstandard

    raw = _make_tar(tmp_path)
    arc = tmp_path / "a.tar.zst"
    with open(raw, "rb") as fin, open(arc, "wb") as fout:
        zstandard.ZstdCompressor().copy_stream(fin, fout)

    payload = (tmp_path / "x").read_bytes()
    src = ABISource.from_archive(arc, UnpackMethod.TAR_ZST)
    members = {p: r() for p, _s, r in src.iter_members()}
    assert members["x"] == payload


def test_tar_lz4_source_streams_members(tmp_path: pathlib.Path) -> None:
    import lz4.frame

    raw = _make_tar(tmp_path)
    arc = tmp_path / "a.tar.lz4"
    with open(raw, "rb") as fin, open(arc, "wb") as fout:
        fout.write(lz4.frame.compress(fin.read()))

    payload = (tmp_path / "x").read_bytes()
    src = ABISource.from_archive(arc, UnpackMethod.TAR_LZ4)
    members = {p: r() for p, _s, r in src.iter_members()}
    assert members["x"] == payload
