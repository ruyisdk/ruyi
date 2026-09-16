import pathlib
import tarfile
import zipfile

from ruyi.ruyipkg.abi.sources import ABISource
from ruyi.ruyipkg.unpack_method import UnpackMethod


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
