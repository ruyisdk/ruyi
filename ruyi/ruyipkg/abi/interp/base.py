"""Interpreter protocol and registry for decoding raw ABI-property blobs.

Interpreters are an additive layer: they read only the generic GnuProperty /
AttributeVendorBlob structures and emit a flat key-value map. A machine with no
registered interpreter still gets full raw capture, just no decoded keys.
"""

from __future__ import annotations

from typing import Mapping, NamedTuple, Protocol, Sequence, runtime_checkable

from ..model import AttributeVendorBlob, GnuProperty


class ArchMetadata(NamedTuple):
    elf_machine: int
    bitness: int
    endianness: str


@runtime_checkable
class AttrInterpreter(Protocol):
    e_machines: frozenset[int]

    def recognize_arch(self, uname_machine: str) -> ArchMetadata | None: ...

    def interpret(
        self,
        gnu_properties: Sequence[GnuProperty],
        elf_attributes: Sequence[AttributeVendorBlob],
        little_endian: bool,
    ) -> dict[str, str | int | bool]: ...

    def rollup(
        self,
        per_file: Sequence[Mapping[str, object]],
    ) -> dict[str, object]: ...

    def host_attrs(self) -> dict[str, str | int | bool]:
        """Probe the running host, in the same key vocabulary as interpret().
        An empty dict means 'cannot determine'."""
        ...

    def check(
        self,
        host: Mapping[str, object],
        required: Mapping[str, object],
    ) -> bool | None:
        """True: host satisfies required; False: definite mismatch;
        None: undetermined."""
        ...


_REGISTRY: dict[int, AttrInterpreter] = {}


def register(interp: AttrInterpreter) -> None:
    for machine in interp.e_machines:
        _REGISTRY[machine] = interp


def get_interpreter(e_machine: int) -> AttrInterpreter | None:
    return _REGISTRY.get(e_machine)


def recognize_arch_by_uname(uname_machine: str | None) -> ArchMetadata | None:
    probe_native = not uname_machine
    if probe_native:
        import platform
        import sys

        uname_machine = platform.machine()
        bitness = sys.maxsize.bit_length() + 1

    assert uname_machine is not None

    for interp in _REGISTRY.values():
        if data := interp.recognize_arch(uname_machine):
            if probe_native:
                # use the bitness and endianness from the running host
                return ArchMetadata(data.elf_machine, bitness, sys.byteorder)
            return data

    return None
