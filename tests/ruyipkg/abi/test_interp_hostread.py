import ctypes
import pathlib
from typing import cast

from pytest import MonkeyPatch

from ruyi.ruyipkg.abi.interp._hostread import read_auxv, read_cpuinfo


def test_read_cpuinfo_returns_contents(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "cpuinfo"
    path.write_text("isa: rv64gc\n", encoding="utf-8")
    assert read_cpuinfo(str(path)) == "isa: rv64gc\n"


def test_read_cpuinfo_missing_returns_empty(tmp_path: pathlib.Path) -> None:
    assert read_cpuinfo(str(tmp_path / "does-not-exist")) == ""


def test_read_auxv_returns_dict_of_ints() -> None:
    # don't trust the return value's declared shape
    result = cast(object, read_auxv())
    assert isinstance(result, dict)
    assert all(isinstance(k, int) and isinstance(v, int) for k, v in result.items())


def test_read_auxv_swallows_failure(monkeypatch: MonkeyPatch) -> None:
    def boom(*args: object, **kwargs: object) -> None:
        raise OSError("no libc")

    monkeypatch.setattr(ctypes, "CDLL", boom)
    assert read_auxv() == {}
