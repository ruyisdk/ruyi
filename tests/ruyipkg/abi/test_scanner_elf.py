import io
import os
import struct

import pytest

from ruyi.ruyipkg.abi.interp import get_interpreter
from ruyi.ruyipkg.abi.model import ElfType
from ruyi.ruyipkg.abi.scanner import scan_elf_stream
from tests.ruyipkg.abi._elfbuilder import build_elf


def _riscv_attr_section(arch: str = "rv64gc") -> bytes:
    attrs = b"\x05" + arch.encode() + b"\x00"  # Tag_RISCV_arch(5)=str
    size = 1 + 4 + len(attrs)
    body = bytes([1]) + struct.pack("<I", size) + attrs
    sub = b"riscv\x00" + body
    return b"A" + struct.pack("<I", 4 + len(sub)) + sub


def _ppc_gnu_attributes_section() -> bytes:
    # A PowerPC .gnu.attributes section (vendor "gnu"): Tag_File(1) holding
    # Tag_GNU_Power_ABI_FP(4)=2 and Tag_GNU_Power_ABI_Vector(8)=2. All tags and
    # values here are < 128, so each is a single-byte ULEB128.
    attrs = b"\x04\x02\x08\x02"
    body = bytes([1]) + struct.pack("<I", 1 + 4 + len(attrs)) + attrs
    sub = b"gnu\x00" + body
    return b"A" + struct.pack("<I", 4 + len(sub)) + sub


def test_scans_synthetic_riscv_elf() -> None:
    data = build_elf(
        e_machine=243,
        sections={".riscv.attributes": (0x70000003, _riscv_attr_section("RV64GC"))},
    )
    rec, errors = scan_elf_stream(
        io.BytesIO(data), paths=("bin/x",), sha256="deadbeef", max_raw_attr_bytes=4096
    )
    assert errors == []
    assert rec is not None
    assert rec.e_machine == 243
    assert rec.elf_class == 64
    assert rec.endianness == "little"
    assert rec.elf_type is ElfType.EXEC
    assert len(rec.elf_attributes) == 1
    assert rec.parsed_attrs["isa"] == "rv64gc"


def test_unknown_machine_keeps_raw_no_parsed() -> None:
    data = build_elf(e_machine=0x9999, sections={})
    rec, errors = scan_elf_stream(
        io.BytesIO(data), paths=("bin/y",), sha256="00", max_raw_attr_bytes=4096
    )
    assert rec is not None
    assert rec.e_machine == 0x9999
    assert rec.parsed_attrs == {}


def test_unhandled_arch_with_attributes_falls_back_gracefully() -> None:
    # ppc64le (EM_PPC64 = 21) has architecture-specific ABI attributes but no
    # registered interpreter. The raw .gnu.attributes must still be captured
    # verbatim, while parsed_attrs stays empty — an absent decoder must never
    # discard data or stigmatize the architecture.
    assert get_interpreter(21) is None

    section = _ppc_gnu_attributes_section()
    data = build_elf(
        e_machine=21,
        sections={".gnu.attributes": (0x6FFFFFF5, section)},  # SHT_GNU_ATTRIBUTES
    )
    rec, errors = scan_elf_stream(
        io.BytesIO(data),
        paths=("usr/lib/libfoo.so",),
        sha256="00",
        max_raw_attr_bytes=4096,
    )

    assert errors == []
    assert rec is not None
    assert rec.e_machine == 21
    # Raw capture is present for the unhandled architecture ...
    assert len(rec.elf_attributes) == 1
    assert rec.elf_attributes[0].vendor == "gnu"
    # The captured blob is the vendor-subsection data (after the "gnu\0" name):
    # Tag_File(1) + u32 size(9) + the four attribute bytes.
    expected_body = bytes([1]) + struct.pack("<I", 9) + b"\x04\x02\x08\x02"
    assert bytes.fromhex(rec.elf_attributes[0].data_hex) == expected_body
    assert rec.elf_attributes[0].truncated is False
    # ... but no friendly keys are produced (empty, not "unsupported").
    assert rec.parsed_attrs == {}



def test_corrupt_stream_yields_error() -> None:
    rec, errors = scan_elf_stream(
        io.BytesIO(b"not an elf"), paths=("bin/z",), sha256="00", max_raw_attr_bytes=4096
    )
    assert rec is None
    assert errors and errors[0].path == "bin/z"


@pytest.mark.skipif(not os.path.exists("/bin/sh"), reason="needs a system ELF")
def test_scans_real_system_binary() -> None:
    path = os.path.realpath("/bin/sh")
    with open(path, "rb") as f:
        rec, errors = scan_elf_stream(
            f, paths=(path,), sha256="00", max_raw_attr_bytes=4096
        )
    assert rec is not None
    # A dynamically-linked system shell needs at least libc and has an interp.
    if rec.is_dynamic:
        assert rec.interpreter is not None
        assert any("libc" in n for n in rec.needed)
