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

# CPU flag sets required for each ISA level, following the glibc hwcaps
# classification.  The v2 baseline also needs the LZCNT instruction; Intel
# reports it as 'abm', AMD usually reports both, so either alias suffices.
_V2_FLAGS = frozenset({"cx16", "lahf_lm", "popcnt", "pni", "sse4_1", "sse4_2", "ssse3"})
_V3_FLAGS = frozenset(
    {"avx", "avx2", "bmi1", "bmi2", "f16c", "fma", "movbe", "osxsave", "xsave"}
)
_V4_FLAGS = frozenset({"avx512f", "avx512bw", "avx512cd", "avx512dq", "avx512vl"})


class X86_64Interpreter:
    e_machines = frozenset({_EM_X86_64})

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

    def host_attrs(self, *, cpuinfo: str | None = None) -> dict[str, str | int | bool]:
        from ._hostread import read_cpuinfo

        text = read_cpuinfo() if cpuinfo is None else cpuinfo
        flags: frozenset[str] = frozenset()
        for line in text.splitlines():
            key, sep, val = line.partition(":")
            if sep and key.strip() == "flags":
                flags = frozenset(val.split())
                break
        level = 1
        if _level_ok(flags, _V2_FLAGS) and _lzcnt_ok(flags):
            level = 2
        if level == 2 and _level_ok(flags, _V3_FLAGS):
            level = 3
        if level == 3 and _level_ok(flags, _V4_FLAGS):
            level = 4
        return {"isa_level": f"v{level}"}

    def check(
        self,
        host: Mapping[str, object],
        required: Mapping[str, object],
    ) -> bool | None:
        need_level = _isa_level_number(required.get("isa_level"))
        have_level = _isa_level_number(host.get("isa_level"))
        if need_level is None or have_level is None:
            return None
        return need_level <= have_level


def _level_ok(flags: frozenset[str], required: frozenset[str]) -> bool:
    return required <= flags


def _lzcnt_ok(flags: frozenset[str]) -> bool:
    return bool({"abm", "lzcnt"} & flags)


def _isa_level_number(value: object) -> int | None:
    """Parse a 'vN' ISA level, or None if the value is not one."""
    if not isinstance(value, str) or not value.startswith("v"):
        return None
    try:
        return int(value[1:])
    except ValueError:
        return None


register(X86_64Interpreter())
