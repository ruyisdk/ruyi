import struct

from ruyi.ruyipkg.abi.interp.x86_64 import X86_64Interpreter
from ruyi.ruyipkg.abi.model import GnuProperty


def _isa_needed(mask: int) -> GnuProperty:
    return GnuProperty(0xC0008002, struct.pack("<I", mask).hex(), False)


def test_level_v3() -> None:
    interp = X86_64Interpreter()
    out = interp.interpret([_isa_needed(0b0111)], [], little_endian=True)
    assert out["isa_level"] == "v3"


def test_absent_property_is_baseline() -> None:
    assert (
        X86_64Interpreter().interpret([], [], little_endian=True)["isa_level"] == "v1"
    )


def test_rollup_minimum_level() -> None:
    interp = X86_64Interpreter()
    out = interp.rollup([{"isa_level": "v3"}, {"isa_level": "v2"}])
    assert out["isa_level"] == "v2"
    assert out["isa_levels"] == ["v2", "v3"]
