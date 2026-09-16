import struct

from ruyi.ruyipkg.abi.containers import parse_gnu_property_note_section


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
    assert parse_gnu_property_note_section(
        b"", is_64bit=True, little_endian=True, max_bytes=4096
    ) == []
