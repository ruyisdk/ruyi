"""Attribute interpreter registry.

Importing this package registers all bundled interpreters as a side effect.
"""

from __future__ import annotations

from .base import AttrInterpreter, get_interpreter, register
from . import aarch64, riscv, x86_64  # noqa: F401

__all__ = ["AttrInterpreter", "get_interpreter", "register"]
