"""Architecture-neutral parsers for ELF ABI-property containers.

These functions operate purely on raw bytes and never import pyelftools'
architecture-aware decoders, so they behave identically for every machine.
"""

from __future__ import annotations

import struct

from .model import AttributeVendorBlob, GnuProperty

_NT_GNU_PROPERTY_TYPE_0 = 5


def _align_up(value: int, align: int) -> int:
    return (value + align - 1) & ~(align - 1)


def parse_gnu_property_note_section(
    data: bytes,
    *,
    is_64bit: bool,
    little_endian: bool,
    max_bytes: int,
) -> list[GnuProperty]:
    endian = "<" if little_endian else ">"
    prop_align = 8 if is_64bit else 4
    out: list[GnuProperty] = []

    off = 0
    n = len(data)
    while off + 12 <= n:
        namesz, descsz, ntype = struct.unpack_from(endian + "III", data, off)
        off += 12
        name = data[off : off + namesz]
        off += _align_up(namesz, 4)
        desc = data[off : off + descsz]
        off += _align_up(descsz, 4)
        if ntype != _NT_GNU_PROPERTY_TYPE_0 or not name.startswith(b"GNU\x00"):
            continue
        out.extend(
            _parse_property_array(
                desc, endian=endian, align=prop_align, max_bytes=max_bytes
            )
        )
    return out


def _parse_property_array(
    desc: bytes,
    *,
    endian: str,
    align: int,
    max_bytes: int,
) -> list[GnuProperty]:
    out: list[GnuProperty] = []
    off = 0
    n = len(desc)
    while off + 8 <= n:
        pr_type, pr_datasz = struct.unpack_from(endian + "II", desc, off)
        off += 8
        blob = desc[off : off + pr_datasz]
        off += _align_up(pr_datasz, align)
        truncated = False
        if len(blob) > max_bytes:
            blob = blob[:max_bytes]
            truncated = True
        out.append(
            GnuProperty(pr_type=pr_type, data_hex=blob.hex(), truncated=truncated)
        )
    return out


def parse_attribute_vendor_blobs(
    data: bytes,
    *,
    little_endian: bool,
    max_bytes: int,
) -> list[AttributeVendorBlob]:
    if not data or data[0:1] != b"A":
        return []

    endian = "<" if little_endian else ">"
    out: list[AttributeVendorBlob] = []
    off = 1
    n = len(data)
    while off + 4 <= n:
        (length,) = struct.unpack_from(endian + "I", data, off)
        if length < 4 or off + length > n:
            break
        sub = data[off : off + length]
        off += length

        vend_end = sub.find(b"\x00", 4)
        if vend_end == -1:
            break
        vendor = sub[4:vend_end].decode("latin-1")
        blob = sub[vend_end + 1 :]

        truncated = False
        if len(blob) > max_bytes:
            blob = blob[:max_bytes]
            truncated = True
        out.append(
            AttributeVendorBlob(
                vendor=vendor, data_hex=blob.hex(), truncated=truncated
            )
        )
    return out
