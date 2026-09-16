import struct

from ruyi.ruyipkg.abi.containers import (
    parse_attribute_vendor_blobs,
    parse_gnu_property_note_section,
)


def _gnu_property_note(props: list[tuple[int, bytes]], *, align: int = 8) -> bytes:
    desc = b""
    for pr_type, pr_data in props:
        desc += struct.pack("<II", pr_type, len(pr_data)) + pr_data
        pad = (-len(pr_data)) % align
        desc += b"\x00" * pad
    name = b"GNU\x00"
    note = struct.pack("<III", len(name), len(desc), 5) + name
    note += desc  # name already 4-aligned; desc already aligned
    return note


def test_parses_single_property() -> None:
    data = _gnu_property_note([(0xC0008002, struct.pack("<I", 7))])
    props = parse_gnu_property_note_section(
        data, is_64bit=True, little_endian=True, max_bytes=4096
    )
    assert len(props) == 1
    assert props[0].pr_type == 0xC0008002
    assert props[0].data_hex == "07000000"
    assert props[0].truncated is False


def test_ignores_non_gnu_notes() -> None:
    name = b"CORE\x00\x00\x00\x00"
    data = struct.pack("<III", 5, 0, 7) + name
    props = parse_gnu_property_note_section(
        data, is_64bit=True, little_endian=True, max_bytes=4096
    )
    assert props == []


def test_truncates_oversized_blob() -> None:
    data = _gnu_property_note([(0xC0000000, b"\xaa" * 100)])
    props = parse_gnu_property_note_section(
        data, is_64bit=True, little_endian=True, max_bytes=8
    )
    assert props[0].truncated is True
    assert len(bytes.fromhex(props[0].data_hex)) == 8


def test_empty_data() -> None:
    assert (
        parse_gnu_property_note_section(
            b"", is_64bit=True, little_endian=True, max_bytes=4096
        )
        == []
    )


def _attr_section(subsections: list[tuple[bytes, bytes]]) -> bytes:
    out = b"A"
    for vendor, vdata in subsections:
        body = vendor + b"\x00" + vdata
        length = 4 + len(body)
        out += struct.pack("<I", length) + body
    return out


def test_parses_single_vendor() -> None:
    data = _attr_section([(b"riscv", b"\x01\x0b\x00\x00\x00\x05rv64gc\x00")])
    blobs = parse_attribute_vendor_blobs(data, little_endian=True, max_bytes=4096)
    assert len(blobs) == 1
    assert blobs[0].vendor == "riscv"
    assert bytes.fromhex(blobs[0].data_hex) == b"\x01\x0b\x00\x00\x00\x05rv64gc\x00"


def test_parses_multiple_vendors() -> None:
    data = _attr_section([(b"riscv", b"\xaa"), (b"gnu", b"\xbb\xcc")])
    blobs = parse_attribute_vendor_blobs(data, little_endian=True, max_bytes=4096)
    assert [b.vendor for b in blobs] == ["riscv", "gnu"]


def test_truncates_oversized_vendor_data() -> None:
    data = _attr_section([(b"riscv", b"\xaa" * 50)])
    blobs = parse_attribute_vendor_blobs(data, little_endian=True, max_bytes=8)
    assert blobs[0].truncated is True
    assert len(bytes.fromhex(blobs[0].data_hex)) == 8


def test_missing_format_byte_returns_empty() -> None:
    assert parse_attribute_vendor_blobs(b"", little_endian=True, max_bytes=4096) == []
    assert (
        parse_attribute_vendor_blobs(b"X\x00", little_endian=True, max_bytes=4096) == []
    )
