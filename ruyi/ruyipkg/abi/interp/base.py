"""Interpreter protocol and registry for decoding raw ABI-property blobs.

Interpreters are an additive layer: they read only the generic GnuProperty /
AttributeVendorBlob structures and emit a flat key-value map. A machine with no
registered interpreter still gets full raw capture, just no decoded keys.
"""

from __future__ import annotations

from typing import Mapping, Protocol, Sequence, runtime_checkable

from ..model import AttributeVendorBlob, GnuProperty


@runtime_checkable
class AttrInterpreter(Protocol):
    e_machines: frozenset[int]

    def interpret(
        self,
        gnu_properties: Sequence[GnuProperty],
        elf_attributes: Sequence[AttributeVendorBlob],
        little_endian: bool = True,
    ) -> dict[str, str | int | bool]: ...

    def rollup(
        self,
        per_file: Sequence[Mapping[str, object]],
    ) -> dict[str, object]: ...


_REGISTRY: dict[int, AttrInterpreter] = {}


def register(interp: AttrInterpreter) -> None:
    for machine in interp.e_machines:
        _REGISTRY[machine] = interp


def get_interpreter(e_machine: int) -> AttrInterpreter | None:
    return _REGISTRY.get(e_machine)
