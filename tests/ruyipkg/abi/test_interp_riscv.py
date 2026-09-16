import struct

from ruyi.ruyipkg.abi.interp.riscv import RiscVInterpreter
from ruyi.ruyipkg.abi.model import AttributeVendorBlob


def _uleb(n: int) -> bytes:
    out = b""
    while True:
        b = n & 0x7F
        n >>= 7
        out += bytes([b | (0x80 if n else 0)])
        if not n:
            return out


def _riscv_blob(
    arch: str = "rv64gc",
    stack_align: int = 16,
    *,
    little_endian: bool = True,
    lead_section: bool = False,
) -> AttributeVendorBlob:
    # Tag_File(1) subsubsection containing Tag_stack_align(4)=int, Tag_arch(5)=str
    fmt = "<I" if little_endian else ">I"
    attrs = _uleb(4) + _uleb(stack_align) + _uleb(5) + arch.encode() + b"\x00"
    main = bytes([1]) + struct.pack(fmt, 1 + 4 + len(attrs)) + attrs
    # An optional empty, non-Tag_File leading subsection whose u32 size must be
    # read in the right byte order for the walker to land on `main`.
    lead = bytes([2]) + struct.pack(fmt, 5) if lead_section else b""
    return AttributeVendorBlob("riscv", (lead + main).hex(), False)


def test_decodes_isa_and_stack_align() -> None:
    out = RiscVInterpreter().interpret(
        [], [_riscv_blob("RV64GC", 16)], little_endian=True
    )
    assert out["isa"] == "rv64gc"
    assert out["stack_align"] == 16


def test_ignores_non_riscv_vendor() -> None:
    blob = AttributeVendorBlob("gnu", "deadbeef", False)
    assert RiscVInterpreter().interpret([], [blob], little_endian=True) == {}


def test_malformed_zero_size_does_not_hang() -> None:
    # A Tag_File sub-subsection declaring size == 0 must not wedge the walker:
    # pre-fix the cursor never advanced and the parse looped forever.
    body = bytes([1]) + struct.pack("<I", 0)
    blob = AttributeVendorBlob("riscv", body.hex(), False)
    assert RiscVInterpreter().interpret([], [blob], little_endian=True) == {}


def test_big_endian_size_field() -> None:
    # A big-endian RISC-V object stores the sub-subsection size big-endian. With
    # a leading (skipped) subsection, only correct byte-order reading of its size
    # lands the walker on the Tag_File carrying the arch string; reading it as
    # little-endian overshoots and the arch is never decoded.
    blob = _riscv_blob("rv64gc", 16, little_endian=False, lead_section=True)
    out_be = RiscVInterpreter().interpret([], [blob], little_endian=False)
    assert out_be["isa"] == "rv64gc"
    assert out_be["stack_align"] == 16

    out_le = RiscVInterpreter().interpret([], [blob], little_endian=True)
    assert "isa" not in out_le


def test_rollup_distinct_isa_set() -> None:
    interp = RiscVInterpreter()
    out = interp.rollup([{"isa": "rv64gc"}, {"isa": "rv64imac"}, {"isa": "rv64gc"}])
    assert out["isa_strings"] == ["rv64gc", "rv64imac"]
