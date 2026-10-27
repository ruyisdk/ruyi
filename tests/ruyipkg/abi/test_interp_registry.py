from typing import Mapping, Sequence

from ruyi.ruyipkg.abi.interp.base import (
    ArchMetadata,
    get_interpreter,
    recognize_arch_by_uname,
    register,
)
from ruyi.ruyipkg.abi.model import AttributeVendorBlob, GnuProperty


class _FakeInterp:
    e_machines = frozenset({0xBEEF})

    def recognize_arch(self, uname_machine: str) -> ArchMetadata | None:
        if uname_machine == "beef64":
            return ArchMetadata(0xBEEF, 64, "big")
        return None

    def interpret(
        self,
        gnu_properties: Sequence[GnuProperty],
        elf_attributes: Sequence[AttributeVendorBlob],
        little_endian: bool = True,
    ) -> dict[str, str | int | bool]:
        return {"ok": True}

    def rollup(self, per_file: Sequence[Mapping[str, object]]) -> dict[str, object]:
        return {}

    def host_attrs(self) -> dict[str, str | int | bool]:
        return {}

    def check(
        self,
        host: Mapping[str, object],
        required: Mapping[str, object],
    ) -> bool | None:
        return None


def test_unknown_machine_returns_none() -> None:
    assert get_interpreter(0x0FFF) is None


def test_register_and_lookup() -> None:
    register(_FakeInterp())
    got = get_interpreter(0xBEEF)
    assert got is not None
    assert got.interpret([], [], little_endian=True) == {"ok": True}


def test_recognize_arch_non_native() -> None:
    register(_FakeInterp())
    got = recognize_arch_by_uname("beef64")
    assert got is not None
    assert got.elf_machine == 0xBEEF
    assert got.bitness == 64
    assert got.endianness == "big"


def test_recognize_arch_unknown() -> None:
    register(_FakeInterp())
    got = recognize_arch_by_uname("lamb32")
    assert got is None
