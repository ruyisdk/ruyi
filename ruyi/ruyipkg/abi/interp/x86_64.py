"""x86-64 ABI attribute interpreter."""

from __future__ import annotations

from typing import Literal, Mapping, Sequence

from ..model import AttributeVendorBlob, GnuProperty
from .base import register

_EM_X86_64 = 62
_GNU_PROPERTY_X86_ISA_1_NEEDED = 0xC0008002

# bit index -> (name, level)
_ISA_BITS = [
    (0, "baseline", 1),
    (1, "v2", 2),
    (2, "v3", 3),
    (3, "v4", 4),
]


class X86_64Interpreter:
    e_machines = frozenset({_EM_X86_64})

    def interpret(
        self,
        gnu_properties: Sequence[GnuProperty],
        elf_attributes: Sequence[AttributeVendorBlob],
        little_endian: bool = True,
    ) -> dict[str, str | int | bool]:
        byteorder: Literal["little", "big"] = "little"
        if not little_endian:
            byteorder = "big"
        mask = 0
        for prop in gnu_properties:
            if prop.pr_type == _GNU_PROPERTY_X86_ISA_1_NEEDED:
                data = bytes.fromhex(prop.data_hex)
                mask = int.from_bytes(data[:4], byteorder)
                break

        level = 1
        for bit, _name, lvl in _ISA_BITS:
            if mask & (1 << bit):
                level = max(level, lvl)
        return {"isa_level": f"v{level}"}

    def rollup(
        self,
        per_file: Sequence[Mapping[str, object]],
    ) -> dict[str, object]:
        levels = sorted({str(f["isa_level"]) for f in per_file if "isa_level" in f})
        out: dict[str, object] = {}
        if levels:
            out["isa_level"] = min(levels, key=lambda s: int(s[1:]))
            out["isa_levels"] = levels
        return out


register(X86_64Interpreter())
