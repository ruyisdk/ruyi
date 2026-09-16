"""Minimal deterministic 64-bit ELF writer for scanner tests."""

from __future__ import annotations

import struct
from typing import Mapping

_EHDR_SIZE = 64
_SHDR_SIZE = 64


def build_elf(
    *,
    e_machine: int,
    sections: Mapping[str, tuple[int, bytes]] = {},
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

    # Lay out section data blobs after the ELF header.
    blobs: list[tuple[str, int, bytes]] = []  # (name, sh_type, data)
    for name, (sh_type, data) in sections.items():
        blobs.append((name, sh_type, data))

    offset = _EHDR_SIZE
    placed: list[tuple[str, int, int, int]] = []  # (name, sh_type, sh_offset, sh_size)
    for name, sh_type, data in blobs:
        placed.append((name, sh_type, offset, len(data)))
        offset += len(data)

    shstrtab_off = offset
    offset += len(shstrtab)
    shoff = offset

    body = bytearray()
    for _name, _sh_type, data in blobs:
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
    ) -> bytes:
        return struct.pack(
            endian + "IIQQQQIIQQ",
            name_offset,  # sh_name
            sh_type,      # sh_type
            0,            # sh_flags
            0,            # sh_addr
            sh_offset,    # sh_offset
            sh_size,      # sh_size
            0,            # sh_link
            0,            # sh_info
            1,            # sh_addralign
            0,            # sh_entsize
        )

    shtable = bytearray()
    shtable += shdr(0, 0, 0, 0)  # SHT_NULL
    for name, sh_type, sh_offset, sh_size in placed:
        shtable += shdr(name_off[name], sh_type, sh_offset, sh_size)
    shtable += shdr(name_off[".shstrtab"], 3, shstrtab_off, len(shstrtab))  # SHT_STRTAB

    e_ident = bytes(
        [0x7F, ord("E"), ord("L"), ord("F"), 2, 1 if little_endian else 2, 1, 0]
    ) + b"\x00" * 8

    ehdr = e_ident + struct.pack(
        endian + "HHIQQQIHHHHHH",
        e_type,        # e_type
        e_machine,     # e_machine
        1,             # e_version
        0,             # e_entry
        0,             # e_phoff
        shoff,         # e_shoff
        0,             # e_flags
        _EHDR_SIZE,    # e_ehsize
        0,             # e_phentsize
        0,             # e_phnum
        _SHDR_SIZE,    # e_shentsize
        total_sections,  # e_shnum
        shstrndx,      # e_shstrndx
    )

    return bytes(ehdr + body + shtable)
