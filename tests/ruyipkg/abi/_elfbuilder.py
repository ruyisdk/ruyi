"""Minimal deterministic 64-bit ELF writer for scanner tests."""

from __future__ import annotations

import struct
from typing import Mapping

_EHDR_SIZE = 64
_SHDR_SIZE = 64


def build_elf(
    *,
    e_machine: int,
    sections: Mapping[str, tuple[int, bytes] | tuple[int, bytes, int, int]] = {},
    e_type: int = 2,
    little_endian: bool = True,
) -> bytes:
    endian = "<" if little_endian else ">"

    # Section name table: index 0 is the empty name.
    names = ["", *sections.keys(), ".shstrtab"]
    shstrtab = bytearray(b"\x00")
    name_off: dict[str, int] = {"": 0}
    for name in names:
        if name in name_off:
            continue
        name_off[name] = len(shstrtab)
        shstrtab += name.encode() + b"\x00"

    # Lay out section data blobs after the ELF header. Each section value is
    # either (sh_type, data) or (sh_type, data, sh_link, sh_info); missing
    # sh_link/sh_info default to 0.
    blobs: list[
        tuple[str, int, bytes, int, int]
    ] = []  # (name, sh_type, data, sh_link, sh_info)
    for name, value in sections.items():
        sh_type, data = value[0], value[1]
        sh_link = value[2] if len(value) > 2 else 0
        sh_info = value[3] if len(value) > 3 else 0
        blobs.append((name, sh_type, data, sh_link, sh_info))

    offset = _EHDR_SIZE
    placed: list[
        tuple[str, int, int, int, int, int]
    ] = []  # (name, sh_type, sh_offset, sh_size, sh_link, sh_info)
    for name, sh_type, data, sh_link, sh_info in blobs:
        placed.append((name, sh_type, offset, len(data), sh_link, sh_info))
        offset += len(data)

    shstrtab_off = offset
    offset += len(shstrtab)
    shoff = offset

    body = bytearray()
    for _name, _sh_type, data, _sh_link, _sh_info in blobs:
        body += data
    body += shstrtab

    # Section headers: NULL, each blob, then .shstrtab.
    total_sections = 1 + len(placed) + 1
    shstrndx = total_sections - 1

    def shdr(
        name_offset: int,
        sh_type: int,
        sh_offset: int,
        sh_size: int,
        sh_link: int = 0,
        sh_info: int = 0,
    ) -> bytes:
        return struct.pack(
            endian + "IIQQQQIIQQ",
            name_offset,  # sh_name
            sh_type,  # sh_type
            0,  # sh_flags
            0,  # sh_addr
            sh_offset,  # sh_offset
            sh_size,  # sh_size
            sh_link,  # sh_link
            sh_info,  # sh_info
            1,  # sh_addralign
            0,  # sh_entsize
        )

    shtable = bytearray()
    shtable += shdr(0, 0, 0, 0)  # SHT_NULL
    for name, sh_type, sh_offset, sh_size, sh_link, sh_info in placed:
        shtable += shdr(name_off[name], sh_type, sh_offset, sh_size, sh_link, sh_info)
    shtable += shdr(name_off[".shstrtab"], 3, shstrtab_off, len(shstrtab))  # SHT_STRTAB

    e_ident = (
        bytes([0x7F, ord("E"), ord("L"), ord("F"), 2, 1 if little_endian else 2, 1, 0])
        + b"\x00" * 8
    )

    ehdr = e_ident + struct.pack(
        endian + "HHIQQQIHHHHHH",
        e_type,  # e_type
        e_machine,  # e_machine
        1,  # e_version
        0,  # e_entry
        0,  # e_phoff
        shoff,  # e_shoff
        0,  # e_flags
        _EHDR_SIZE,  # e_ehsize
        0,  # e_phentsize
        0,  # e_phnum
        _SHDR_SIZE,  # e_shentsize
        total_sections,  # e_shnum
        shstrndx,  # e_shstrndx
    )

    return bytes(ehdr + body + shtable)
