import struct

from ruyi.ruyipkg.abi.interp.aarch64 import AArch64Interpreter
from ruyi.ruyipkg.abi.model import GnuProperty


def _feature(mask: int) -> GnuProperty:
    return GnuProperty(0xC0000000, struct.pack("<I", mask).hex(), False)


def test_bti_pac_flags() -> None:
    out = AArch64Interpreter().interpret([_feature(0b11)], [])
    assert out["bti"] is True
    assert out["pac"] is True


def test_absent_property_all_false() -> None:
    out = AArch64Interpreter().interpret([], [])
    assert out["bti"] is False
    assert out["pac"] is False


def test_rollup_conservative_and() -> None:
    interp = AArch64Interpreter()
    out = interp.rollup([{"bti": True, "pac": True}, {"bti": True, "pac": False}])
    assert out["bti"] is True
    assert out["pac"] is False
