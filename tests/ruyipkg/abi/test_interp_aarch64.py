import struct

from ruyi.ruyipkg.abi.interp.aarch64 import AArch64Interpreter
from ruyi.ruyipkg.abi.model import GnuProperty


def _feature(mask: int, *, little_endian: bool = True) -> GnuProperty:
    fmt = "<I" if little_endian else ">I"
    return GnuProperty(0xC0000000, struct.pack(fmt, mask).hex(), False)


def test_bti_pac_flags() -> None:
    out = AArch64Interpreter().interpret([_feature(0b11)], [], little_endian=True)
    assert out["bti"] is True
    assert out["pac"] is True


def test_absent_property_all_false() -> None:
    out = AArch64Interpreter().interpret([], [], little_endian=True)
    assert out["bti"] is False
    assert out["pac"] is False


def test_big_endian_feature_decode() -> None:
    # aarch64_be stores the FEATURE_1_AND word big-endian. Decoding it as
    # big-endian must recover BTI|PAC; decoding the same bytes as little-endian
    # must NOT, proving the byte order is actually honored.
    prop = _feature(0b11, little_endian=False)
    out_be = AArch64Interpreter().interpret([prop], [], little_endian=False)
    assert out_be["bti"] is True
    assert out_be["pac"] is True

    out_le = AArch64Interpreter().interpret([prop], [], little_endian=True)
    assert out_le["bti"] is False
    assert out_le["pac"] is False


def test_rollup_conservative_and() -> None:
    interp = AArch64Interpreter()
    out = interp.rollup([{"bti": True, "pac": True}, {"bti": True, "pac": False}])
    assert out["bti"] is True
    assert out["pac"] is False
