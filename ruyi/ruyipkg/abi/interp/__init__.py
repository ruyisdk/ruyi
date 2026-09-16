"""Attribute interpreter registry.

Importing this package registers all bundled interpreters as a side effect.
"""

from __future__ import annotations

from .base import AttrInterpreter, get_interpreter, register

__all__ = ["AttrInterpreter", "get_interpreter", "register"]
