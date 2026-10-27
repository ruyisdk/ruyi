"""RISC-V ABI attribute interpreter."""

from __future__ import annotations

import struct
from typing import Mapping, Sequence

from ..model import AttributeVendorBlob, GnuProperty
from .base import ArchMetadata, register

_EM_RISCV = 243
_TAG_FILE = 1
_TAG_RISCV_STACK_ALIGN = 4
_TAG_RISCV_ARCH = 5


def _read_uleb128(data: bytes, off: int) -> tuple[int, int]:
    result = 0
    shift = 0
    while off < len(data):
        byte = data[off]
        off += 1
        result |= (byte & 0x7F) << shift
        if not byte & 0x80:
            break
        shift += 7
    return result, off


def _read_ntbs(data: bytes, off: int) -> tuple[str, int]:
    end = data.find(b"\x00", off)
    if end == -1:
        end = len(data)
    return data[off:end].decode("latin-1"), end + 1


class RiscVInterpreter:
    e_machines = frozenset({_EM_RISCV})

    def recognize_arch(self, uname_machine: str) -> ArchMetadata | None:
        if not uname_machine.startswith("riscv"):
            return None
        try:
            bitness = int(uname_machine[5:])
        except ValueError:
            return None
        # XXX Big-endian RISC-V is not widespread, and isn't detectable from
        # utsname.machine alone. Assume little-endian for now.
        return ArchMetadata(_EM_RISCV, bitness, "little")

    def interpret(
        self,
        gnu_properties: Sequence[GnuProperty],
        elf_attributes: Sequence[AttributeVendorBlob],
        little_endian: bool,
    ) -> dict[str, str | int | bool]:
        out: dict[str, str | int | bool] = {}
        for blob in elf_attributes:
            if blob.vendor != "riscv":
                continue
            self._parse_vendor_body(
                bytes.fromhex(blob.data_hex), out, little_endian=little_endian
            )
        return out

    def _parse_vendor_body(
        self,
        body: bytes,
        out: dict[str, str | int | bool],
        *,
        little_endian: bool,
    ) -> None:
        size_fmt = "<I" if little_endian else ">I"
        off = 0
        n = len(body)
        while off < n:
            tag = body[off]
            off += 1
            if off + 4 > n:
                break
            (size,) = struct.unpack_from(size_fmt, body, off)
            off += 4
            if size < 5:
                break
            attr_end = off - 5 + size
            if tag != _TAG_FILE:
                off = attr_end
                continue
            self._parse_file_attrs(body, off, min(attr_end, n), out)
            off = attr_end

    def _parse_file_attrs(
        self, body: bytes, off: int, end: int, out: dict[str, str | int | bool]
    ) -> None:
        while off < end:
            attr_tag, off = _read_uleb128(body, off)
            if attr_tag % 2 == 1:  # odd -> string
                value, off = _read_ntbs(body, off)
                if attr_tag == _TAG_RISCV_ARCH:
                    out["isa"] = value.lower()
            else:  # even -> uleb128 int
                ivalue, off = _read_uleb128(body, off)
                if attr_tag == _TAG_RISCV_STACK_ALIGN:
                    out["stack_align"] = ivalue

    def rollup(
        self,
        per_file: Sequence[Mapping[str, object]],
    ) -> dict[str, object]:
        isas = sorted({str(f["isa"]) for f in per_file if "isa" in f})
        return {"isa_strings": isas} if isas else {}

    def host_attrs(self, *, cpuinfo: str | None = None) -> dict[str, str | int | bool]:
        from ._hostread import read_cpuinfo

        text = read_cpuinfo() if cpuinfo is None else cpuinfo
        for line in text.splitlines():
            key, sep, val = line.partition(":")
            if sep and key.strip() == "isa":
                isa = val.strip().lower()
                if isa:
                    return {"isa": isa}
        return {}

    def check(
        self,
        host: Mapping[str, object],
        required: Mapping[str, object],
    ) -> bool | None:
        need, have = required.get("isa"), host.get("isa")
        if not isinstance(need, str) or not isinstance(have, str):
            return None
        need_set, have_set = _isa_extensions(need), _isa_extensions(have)
        if need_set is None or have_set is None:
            return None
        return need_set <= have_set


_G_EXPANSION = frozenset({"i", "m", "a", "f", "d", "zicsr", "zifencei"})


def _isa_extensions(isa: str) -> frozenset[str] | None:
    """Split a RISC-V ISA string into an extension set, or None if unparsable.

    Handles the canonical form rvNN[i|e|g]<letters>[_<multi>...] with optional
    version suffixes; 'g' expands per the base spec. XLEN is folded into the
    result as xlenNN, so a cross-XLEN requirement is a definite mismatch.
    """
    import re

    m = re.fullmatch(r"rv(32|64|128)([a-z0-9]+(?:_[a-z0-9]+)*)", isa)
    if m is None:
        return None
    xlen, rest = m.group(1), m.group(2)
    first, *multi = rest.split("_")
    if not first or first[0] not in "ieg":
        return None

    def strip_ver(tok: str) -> str:
        return re.sub(r"\d+p\d+$|\d+$", "", tok)

    exts: set[str] = set()
    base = first[0]
    exts |= _G_EXPANSION if base == "g" else {base}
    for ch in strip_ver(first[1:]):
        exts.add(ch)
    for tok in multi:
        tok = strip_ver(tok)
        if not tok:
            return None
        exts.add(tok)
    exts.discard("")
    return frozenset(exts) | {f"xlen{xlen}"}


register(RiscVInterpreter())
