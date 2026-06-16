import pathlib
import tarfile
import tempfile
import zipfile

import pytest

from ruyi.ruyipkg.install_size import compute_install_size
from ruyi.ruyipkg.unpack_method import UnpackMethod


@pytest.fixture
def test_dir() -> str:
    d = tempfile.mkdtemp()
    (pathlib.Path(d) / "a.txt").write_text("hello")
    (pathlib.Path(d) / "b.txt").write_text("world!")
    sub = pathlib.Path(d) / "sub"
    sub.mkdir()
    (sub / "c.txt").write_text("ok")
    return d


@pytest.fixture
def tar_gz_path(test_dir: str) -> str:
    p = tempfile.mktemp(suffix=".tar.gz")
    with tarfile.open(p, "w:gz") as tf:
        tf.add(test_dir, arcname=".")
    return p


@pytest.fixture
def zip_path(test_dir: str) -> str:
    import os

    p = tempfile.mktemp(suffix=".zip")
    with zipfile.ZipFile(p, "w") as zf:
        for root, _dirs, files in os.walk(test_dir):
            for f in files:
                full = pathlib.Path(root) / f
                zf.write(full, full.relative_to(test_dir))
    return p


def test_tar_gz(tar_gz_path: str) -> None:
    size = compute_install_size(pathlib.Path(tar_gz_path), UnpackMethod.TAR_GZ)
    assert size == 13  # a.txt(5) + b.txt(6) + sub/c.txt(2)


def test_zip(zip_path: str) -> None:
    size = compute_install_size(pathlib.Path(zip_path), UnpackMethod.ZIP)
    assert size == 13


def test_raw(test_dir: str) -> None:
    p = pathlib.Path(test_dir) / "a.txt"
    size = compute_install_size(p, UnpackMethod.RAW)
    assert size == p.stat().st_size
    assert size == 5


def test_unknown_method_raises() -> None:
    with pytest.raises(ValueError, match="unsupported unpack method"):
        compute_install_size(pathlib.Path("dummy"), UnpackMethod.UNKNOWN)
