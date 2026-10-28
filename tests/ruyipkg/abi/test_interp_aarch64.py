import struct

from ruyi.ruyipkg.abi.interp.aarch64 import AArch64Interpreter
from ruyi.ruyipkg.abi.model import GnuProperty

_AT_HWCAP, _AT_HWCAP2 = 16, 26
_HWCAP_PACA, _HWCAP_PACG = 1 << 30, 1 << 31
_HWCAP2_SVE2 = 1 << 1
_HWCAP2_BTI = 1 << 17


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


def test_host_attrs_from_auxv() -> None:
    interp = AArch64Interpreter()
    assert interp.host_attrs(
        auxv={_AT_HWCAP: _HWCAP_PACA, _AT_HWCAP2: _HWCAP2_BTI}
    ) == {
        "bti": True,
        "pac": True,
    }
    assert interp.host_attrs(auxv={_AT_HWCAP: 0, _AT_HWCAP2: 0}) == {
        "bti": False,
        "pac": False,
    }
    assert interp.host_attrs(auxv={}) == {}


def test_bti_is_not_hwcap2_sve2() -> None:
    # HWCAP2 bit 1 advertises SVE2, not BTI. Only bit 17 means BTI.
    out = AArch64Interpreter().host_attrs(
        auxv={_AT_HWCAP: 0, _AT_HWCAP2: _HWCAP2_SVE2}
    )
    assert out == {"bti": False, "pac": False}


def test_check_degrades_to_unknown_not_incompatible() -> None:
    interp = AArch64Interpreter()
    # BTI required, host has it: fine.
    assert (
        interp.check({"bti": True, "pac": False}, {"bti": True, "pac": False}) is True
    )
    # BTI required, host lacks it: runs (hint space), feature inert -> None.
    assert (
        interp.check({"bti": False, "pac": False}, {"bti": True, "pac": False}) is None
    )
    # Nothing required: fine regardless.
    assert interp.check({}, {"bti": False, "pac": False}) is True
