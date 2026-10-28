import ctypes
import pathlib

from pytest import MonkeyPatch

from ruyi.ruyipkg.abi.interp._hostread import read_auxv, read_cpuinfo


def test_read_cpuinfo_returns_contents(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "cpuinfo"
    path.write_text("isa: rv64gc\n", encoding="utf-8")
    assert read_cpuinfo(str(path)) == "isa: rv64gc\n"


def test_read_cpuinfo_missing_returns_empty(tmp_path: pathlib.Path) -> None:
    assert read_cpuinfo(str(tmp_path / "does-not-exist")) == ""


class _FakeGetauxval:
    restype: object = None

    def __call__(self, at: ctypes.c_ulong) -> int:
        return {16: 0x1234, 26: 0x5678}.get(at.value, 0)


class _FakeLibc:
    def __init__(self) -> None:
        self.getauxval = _FakeGetauxval()


def test_read_auxv_reads_expected_entries(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(ctypes, "CDLL", lambda name: _FakeLibc())
    assert read_auxv() == {16: 0x1234, 26: 0x5678}


def test_read_auxv_falls_back_to_libc_soname(monkeypatch: MonkeyPatch) -> None:
    calls: list[str | None] = []

    def fake_cdll(name: str | None) -> _FakeLibc:
        calls.append(name)
        if name is None:
            # No process-local symbol table, as on a statically linked libc.
            raise OSError("no such process symbols")
        return _FakeLibc()

    monkeypatch.setattr(ctypes, "CDLL", fake_cdll)
    assert read_auxv() == {16: 0x1234, 26: 0x5678}
    assert calls == [None, "libc.so.6"]


def test_read_auxv_swallows_failure(monkeypatch: MonkeyPatch) -> None:
    def boom(*args: object, **kwargs: object) -> None:
        raise OSError("no libc")

    monkeypatch.setattr(ctypes, "CDLL", boom)
    assert read_auxv() == {}
