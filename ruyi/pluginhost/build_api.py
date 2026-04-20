"""Build-recipe-only additions to the RuyiHostAPI.

Only reachable from inside a phctx where ``recipe_project_root`` is set
(which in turn causes the ``build-recipe-v1`` capability to be granted
and ``call-subprocess-v1`` to be revoked).

At load time the recipe module gets a ``RUYI.build`` namespace exposing
:meth:`RuyiBuildRecipeAPI.schedule_build`. At build time, each scheduled
callable is invoked with a :class:`RecipeBuildCtx` that returns plans
(:class:`Invocation`, :class:`Artifact`) rather than executing anything.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Mapping, NamedTuple
import pathlib

from ..ruyipkg.recipe_project import RecipeProject, safe_join

if TYPE_CHECKING:
    from .ctx import PluginHostContext
    from .traits import SupportsEvalFunction, SupportsGetOption


class ScheduledBuild(NamedTuple):
    """A single build registered by a recipe at load time."""

    name: str
    fn: object
    recipe_file: pathlib.Path


@dataclass(frozen=True)
class Invocation:
    """A declarative plan for a single subprocess invocation.

    Produced by ``ctx.subprocess(...)``. The executor (B7) is responsible
    for actually running it and, after a zero-exit, resolving the
    :class:`Artifact` globs in :attr:`produces`.
    """

    argv: tuple[str, ...]
    cwd: pathlib.Path
    env: Mapping[str, str] = field(default_factory=dict)
    produces: tuple["Artifact", ...] = ()


@dataclass(frozen=True)
class Artifact:
    """A declared build output matched against a glob under ``root``."""

    glob: str
    root: pathlib.Path


class RuyiBuildRecipeAPI:
    """The ``RUYI.build`` namespace for build-recipe modules (load time)."""

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


_MISSING = object()


class RecipeBuildCtx:
    """The per-build ``ctx`` object passed to each scheduled callable.

    All methods return *plans* — they do not execute subprocesses or
    touch the filesystem beyond path resolution and traversal checks.
    """

    def __init__(
        self,
        project: RecipeProject,
        name: str,
        recipe_file: pathlib.Path,
        user_vars: Mapping[str, str],
    ) -> None:
        self._project = project
        self._name = name
        self._recipe_file = recipe_file
        self._user_vars = dict(user_vars)

    @property
    def name(self) -> str:
        return self._name

    @property
    def recipe_file(self) -> str:
        return str(self._recipe_file)

    @property
    def repo_root(self) -> str:
        return str(self._project.root)

    def repo_path(self, rel: str) -> str:
        return str(safe_join(self._project.root, rel))

    def var(self, name: str, default: object = _MISSING) -> str:
        if name in self._user_vars:
            return self._user_vars[name]
        if default is _MISSING:
            raise RuntimeError(
                f"ctx.var: no value provided for {name!r} and no default given"
            )
        if not isinstance(default, str):
            raise RuntimeError(
                f"ctx.var: default for {name!r} must be a string "
                f"(got {type(default).__name__})"
            )
        return default

    def subprocess(
        self,
        argv: list[str] | tuple[str, ...],
        cwd: str | None = None,
        env: Mapping[str, str] | None = None,
        produces: list["Artifact"] | tuple["Artifact", ...] = (),
    ) -> Invocation:
        if not argv:
            raise RuntimeError("ctx.subprocess: argv must be non-empty")
        if not all(isinstance(x, str) for x in argv):
            raise RuntimeError("ctx.subprocess: argv entries must be strings")

        resolved_cwd = self._project.root if cwd is None else pathlib.Path(cwd)
        env_map = dict(env) if env is not None else {}
        produces_tuple = tuple(produces)
        for a in produces_tuple:
            if not isinstance(a, Artifact):
                raise RuntimeError(
                    "ctx.subprocess: produces entries must be Artifact values "
                    "(returned by ctx.artifact(...))"
                )
        return Invocation(
            argv=tuple(argv),
            cwd=resolved_cwd,
            env=env_map,
            produces=produces_tuple,
        )

    def artifact(
        self,
        glob: str,
        root: str | None = None,
    ) -> Artifact:
        if not glob:
            raise RuntimeError("ctx.artifact: glob must be a non-empty string")

        if root is None:
            resolved_root = self._project.output_dir
        else:
            root_path = pathlib.Path(root)
            if root_path.is_absolute():
                resolved_root = root_path.resolve()
                allowed_by_extras = any(
                    resolved_root == extra or resolved_root.is_relative_to(extra)
                    for extra in self._project.extra_artifact_roots
                )
                if not allowed_by_extras and (
                    not resolved_root.is_relative_to(self._project.root.resolve())
                ):
                    raise RuntimeError(
                        f"ctx.artifact: absolute root {resolved_root} is not in "
                        f"extra_artifact_roots and not inside the project"
                    )
            else:
                resolved_root = safe_join(self._project.root, root)

        return Artifact(glob=glob, root=resolved_root)
