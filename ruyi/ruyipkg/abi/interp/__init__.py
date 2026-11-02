"""Attribute interpreter registry.

Importing this package registers all bundled interpreters as a side effect.
"""

from __future__ import annotations

from .base import (
    ArchMetadata,
    AttrInterpreter,
    get_interpreter,
    recognize_arch_by_uname,
    register,
)
from . import aarch64, riscv, x86_64  # noqa: F401

__all__ = [
    "ArchMetadata",
    "AttrInterpreter",
    "get_interpreter",
    "recognize_arch_by_uname",
    "register",
]
