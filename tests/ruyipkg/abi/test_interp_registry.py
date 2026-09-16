from typing import Mapping, Sequence

from ruyi.ruyipkg.abi.interp.base import get_interpreter, register
from ruyi.ruyipkg.abi.model import AttributeVendorBlob, GnuProperty


class _FakeInterp:
    e_machines = frozenset({0xBEEF})

    def interpret(
        self,
        gnu_properties: Sequence[GnuProperty],
        elf_attributes: Sequence[AttributeVendorBlob],
        little_endian: bool = True,
    ) -> dict[str, str | int | bool]:
        return {"ok": True}

    def rollup(self, per_file: Sequence[Mapping[str, object]]) -> dict[str, object]:
        return {}


def test_unknown_machine_returns_none() -> None:
    assert get_interpreter(0x0FFF) is None


def test_register_and_lookup() -> None:
    register(_FakeInterp())
    got = get_interpreter(0xBEEF)
    assert got is not None
    assert got.interpret([], [], little_endian=True) == {"ok": True}
