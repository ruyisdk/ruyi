"""Build-recipe-only additions to the RuyiHostAPI.

Only reachable from inside a phctx where ``recipe_project_root`` is set
(which in turn causes the ``build-recipe-v1`` capability to be granted
and ``call-subprocess-v1`` to be revoked).

At load time the recipe module gets a ``RUYI.build`` namespace exposing
:meth:`RuyiBuildRecipeAPI.schedule_build`; later phases (B6+) will add
the per-invocation ``ctx`` object and an executor.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, NamedTuple
import pathlib

if TYPE_CHECKING:
    from .ctx import PluginHostContext
    from .traits import SupportsEvalFunction, SupportsGetOption


class ScheduledBuild(NamedTuple):
    """A single build registered by a recipe at load time."""

    name: str
    fn: object
    recipe_file: pathlib.Path


class RuyiBuildRecipeAPI:
    """The ``RUYI.build`` namespace for build-recipe modules."""

    def __init__(
        self,
        phctx: "PluginHostContext[SupportsGetOption, SupportsEvalFunction]",
        recipe_file: pathlib.Path,
    ) -> None:
        self._phctx = phctx
        self._recipe_file = recipe_file

    def schedule_build(
        self,
        fn: object,
        name: str | None = None,
    ) -> None:
        """Register a scheduled build callable.

        Must be called at module top level. ``name`` defaults to the
        callable's ``__name__``; duplicate names within the same recipe
        file raise :class:`RuntimeError`.
        """

        if not callable(fn):
            raise RuntimeError(
                f"schedule_build: expected a callable, got {type(fn).__name__}"
            )

        resolved_name = name if name is not None else getattr(fn, "__name__", None)
        if not isinstance(resolved_name, str) or not resolved_name:
            raise RuntimeError(
                "schedule_build: could not derive a name from the callable; "
                "pass name=... explicitly"
            )

        registry = self._phctx.scheduled_builds_for(self._recipe_file)
        if any(sb.name == resolved_name for sb in registry):
            raise RuntimeError(
                f"schedule_build: duplicate build name {resolved_name!r} "
                f"in recipe {self._recipe_file}"
            )
        registry.append(
            ScheduledBuild(
                name=resolved_name,
                fn=fn,
                recipe_file=self._recipe_file,
            )
        )
