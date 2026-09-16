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


def _riscv_blob(arch: str = "rv64gc", stack_align: int = 16) -> AttributeVendorBlob:
    # Tag_File(1) subsubsection containing Tag_stack_align(4)=int, Tag_arch(5)=str
    attrs = _uleb(4) + _uleb(stack_align) + _uleb(5) + arch.encode() + b"\x00"
    size = 1 + 4 + len(attrs)
    body = bytes([1]) + struct.pack("<I", size) + attrs
    return AttributeVendorBlob("riscv", body.hex(), False)


def test_decodes_isa_and_stack_align() -> None:
    out = RiscVInterpreter().interpret([], [_riscv_blob("RV64GC", 16)])
    assert out["isa"] == "rv64gc"
    assert out["stack_align"] == 16


def test_ignores_non_riscv_vendor() -> None:
    blob = AttributeVendorBlob("gnu", "deadbeef", False)
    assert RiscVInterpreter().interpret([], [blob]) == {}


def test_rollup_distinct_isa_set() -> None:
    interp = RiscVInterpreter()
    out = interp.rollup([{"isa": "rv64gc"}, {"isa": "rv64imac"}, {"isa": "rv64gc"}])
    assert out["isa_strings"] == ["rv64gc", "rv64imac"]
