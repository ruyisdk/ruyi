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

    def host_attrs(
        self, *, auxv: Mapping[int, int] | None = None
    ) -> dict[str, str | int | bool]:
        from ._hostread import read_auxv

        values = read_auxv() if auxv is None else auxv
        if not values:
            return {}
        hwcap = values.get(16, 0)  # AT_HWCAP
        hwcap2 = values.get(26, 0)  # AT_HWCAP2
        return {
            "bti": bool(hwcap2 & (1 << 1)),  # HWCAP2_BTI
            "pac": bool(hwcap & ((1 << 30) | (1 << 31))),  # HWCAP_PACA|HWCAP_PACG
        }

    def check(
        self,
        host: Mapping[str, object],
        required: Mapping[str, object],
    ) -> bool | None:
        degraded = False
        for key in ("bti", "pac"):
            if not required.get(key):
                continue
            if key not in host:
                return None
            if not host[key]:
                # Both features live in hint space, so a host without
                # support executes the instructions as no-ops.
                degraded = True
        return None if degraded else True


register(AArch64Interpreter())
