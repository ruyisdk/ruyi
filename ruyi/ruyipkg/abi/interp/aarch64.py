"""AArch64 ABI attribute interpreter."""

from __future__ import annotations

from typing import Literal, Mapping, Sequence

from ..model import AttributeVendorBlob, GnuProperty
from .base import register

_EM_AARCH64 = 183
_GNU_PROPERTY_AARCH64_FEATURE_1_AND = 0xC0000000
_FEATURE_1_BTI = 1 << 0
_FEATURE_1_PAC = 1 << 1


class AArch64Interpreter:
    e_machines = frozenset({_EM_AARCH64})

    def interpret(
        self,
        gnu_properties: Sequence[GnuProperty],
        elf_attributes: Sequence[AttributeVendorBlob],
        little_endian: bool,
    ) -> dict[str, str | int | bool]:
        byteorder: Literal["little", "big"] = "little"
        if not little_endian:
            byteorder = "big"
        mask = 0
        for prop in gnu_properties:
            if prop.pr_type == _GNU_PROPERTY_AARCH64_FEATURE_1_AND:
                data = bytes.fromhex(prop.data_hex)
                mask = int.from_bytes(data[:4], byteorder)
                break
        return {
            "bti": bool(mask & _FEATURE_1_BTI),
            "pac": bool(mask & _FEATURE_1_PAC),
        }

    def rollup(
        self,
        per_file: Sequence[Mapping[str, object]],
    ) -> dict[str, object]:
        if not per_file:
            return {}
        return {
            "bti": all(bool(f.get("bti")) for f in per_file),
            "pac": all(bool(f.get("pac")) for f in per_file),
        }


register(AArch64Interpreter())
