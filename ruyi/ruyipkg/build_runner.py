"""Executor for ``ruyi admin build-package``.

Given a path to a recipe ``.star`` file, this module:

1. Discovers the enclosing recipe project (via :mod:`recipe_project`).
2. Builds a :class:`PluginHostContext` in build-recipe mode.
3. Loads the recipe module, collecting :class:`ScheduledBuild`
   registrations.
4. For each (optionally ``--name``-filtered) scheduled build, constructs
   a :class:`RecipeBuildCtx` and calls the registered callable to obtain
   one or more :class:`Invocation` plans.
5. Executes each plan via :func:`subprocess.run` unless ``dry_run`` is
   set; on a zero exit, resolves declared ``produces`` globs, computes
   sha256/sha512/size for each matched file, and writes a build-report
   TOML.

The runner is intentionally I/O-heavy at call time and light on imports
at the module top level so that the CLI startup-flow lint stays happy;
all subprocess/hashlib/tomllib usage is inside :func:`run_recipe`.
"""

from __future__ import annotations

from dataclasses import dataclass
import pathlib
from typing import TYPE_CHECKING, Any, Iterable, Mapping, Sequence

from ..log import RuyiLogger
from ..pluginhost.build_api import (
    Invocation,
    RecipeBuildCtx,
    ScheduledBuild,
)
from .recipe_project import RecipeProject, discover_recipe_project

if TYPE_CHECKING:
    from ..pluginhost.ctx import PluginHostContext


@dataclass(frozen=True)
class ArtifactReport:
    path: pathlib.Path
    size: int
    checksums: Mapping[str, str]


@dataclass(frozen=True)
class BuildReport:
    recipe_file: pathlib.Path
    project_name: str
    build_name: str
    invocations: tuple[Invocation, ...]
    artifacts: tuple[ArtifactReport, ...]
    exit_code: int


class BuildFailure(RuntimeError):
    """Raised when an Invocation exits non-zero."""

    def __init__(self, build_name: str, exit_code: int) -> None:
        super().__init__(f"build {build_name!r} failed with exit code {exit_code}")
        self.build_name = build_name
        self.exit_code = exit_code


def run_recipe(
    logger: RuyiLogger,
    recipe_file: pathlib.Path,
    *,
    user_vars: Mapping[str, str] | None = None,
    selected_names: Sequence[str] | None = None,
    dry_run: bool = False,
    output_dir_override: pathlib.Path | None = None,
) -> list[BuildReport]:
    """Load the recipe and execute (or plan, if ``dry_run``) each selected
    scheduled build.

    Returns a :class:`BuildReport` per executed build. Raises
    :class:`BuildFailure` on the first non-zero exit (subsequent builds
    are not attempted).
    """

    project = discover_recipe_project(recipe_file)
    if output_dir_override is not None:
        project = _with_output_dir(project, output_dir_override)

    phctx = _make_recipe_phctx(logger, project)
    scheduled = _load_recipe_module(phctx, recipe_file)
    if not scheduled:
        raise RuntimeError(
            f"recipe {recipe_file} scheduled no builds "
            f"(did you call RUYI.build.schedule_build(...)?)"
        )

    if selected_names is not None:
        selected = _filter_by_name(scheduled, selected_names)
    else:
        selected = list(scheduled)

    reports: list[BuildReport] = []
    for sb in selected:
        reports.append(
            _execute_one_build(
                logger,
                phctx,
                project,
                sb,
                user_vars=user_vars or {},
                dry_run=dry_run,
            )
        )
    return reports


def _with_output_dir(
    project: RecipeProject, new_output_dir: pathlib.Path
) -> RecipeProject:
    resolved = new_output_dir.resolve()
    return RecipeProject(
        root=project.root,
        name=project.name,
        output_dir=resolved,
        extra_artifact_roots=project.extra_artifact_roots,
    )


def _make_recipe_phctx(
    logger: RuyiLogger, project: RecipeProject
) -> "PluginHostContext[Any, Any]":
    # Local import: keeps heavy module-load chains out of CLI startup.
    from ..pluginhost.ctx import PluginHostContext

    return PluginHostContext.new(
        logger,
        project.root,  # plugin_root is reused for the recipe project
        recipe_project_root=project.root,
    )


def _load_recipe_module(
    phctx: "PluginHostContext[Any, Any]", recipe_file: pathlib.Path
) -> list[ScheduledBuild]:
    resolved = recipe_file.resolve(strict=True)
    return phctx.load_recipe(resolved)


def _filter_by_name(
    scheduled: Iterable[ScheduledBuild], wanted: Sequence[str]
) -> list[ScheduledBuild]:
    by_name = {sb.name: sb for sb in scheduled}
    missing = [n for n in wanted if n not in by_name]
    if missing:
        raise RuntimeError(
            f"recipe does not define the requested build(s): {', '.join(missing)}"
        )
    return [by_name[n] for n in wanted]


def _execute_one_build(
    logger: RuyiLogger,
    phctx: "PluginHostContext[Any, Any]",
    project: RecipeProject,
    sb: ScheduledBuild,
    *,
    user_vars: Mapping[str, str],
    dry_run: bool,
) -> BuildReport:
    ctx = RecipeBuildCtx(
        project=project,
        name=sb.name,
        recipe_file=sb.recipe_file,
        user_vars=user_vars,
    )
    ev = phctx.make_evaluator()
    result = ev.eval_function(sb.fn, ctx)
    invocations = _normalize_invocations(sb.name, result)

    if dry_run:
        for inv in invocations:
            logger.I(f"[dry-run] would run: {' '.join(inv.argv)} (cwd={inv.cwd})")
        return BuildReport(
            recipe_file=sb.recipe_file,
            project_name=project.name,
            build_name=sb.name,
            invocations=tuple(invocations),
            artifacts=(),
            exit_code=0,
        )

    last_exit = 0
    for inv in invocations:
        last_exit = _run_invocation(logger, inv)
        if last_exit != 0:
            raise BuildFailure(sb.name, last_exit)

    artifact_reports = _resolve_artifacts(invocations)

    return BuildReport(
        recipe_file=sb.recipe_file,
        project_name=project.name,
        build_name=sb.name,
        invocations=tuple(invocations),
        artifacts=tuple(artifact_reports),
        exit_code=last_exit,
    )


def _normalize_invocations(build_name: str, result: object) -> list[Invocation]:
    if isinstance(result, Invocation):
        return [result]
    if isinstance(result, (list, tuple)):
        out: list[Invocation] = []
        for item in result:
            if not isinstance(item, Invocation):
                raise RuntimeError(
                    f"build {build_name!r}: expected Invocation (from "
                    f"ctx.subprocess), got {type(item).__name__}"
                )
            out.append(item)
        if not out:
            raise RuntimeError(
                f"build {build_name!r}: returned an empty list of Invocations"
            )
        return out
    raise RuntimeError(
        f"build {build_name!r}: expected Invocation or list of Invocations, "
        f"got {type(result).__name__}"
    )


def _run_invocation(logger: RuyiLogger, inv: Invocation) -> int:
    import os
    import subprocess

    logger.I(f"running: {' '.join(inv.argv)} (cwd={inv.cwd})")
    merged_env = os.environ.copy()
    merged_env.update(inv.env)

    # SECURITY: recipes are explicit Starlark code evaluated in a trusted recipe
    # project, and the invocation takes an argv list with no shell expansion,
    # which is the documented threat model.
    proc = subprocess.run(
        list(inv.argv),
        cwd=str(inv.cwd),
        env=merged_env,
        check=False,
    )
    return proc.returncode


def _resolve_artifacts(
    invocations: Iterable[Invocation],
) -> list[ArtifactReport]:
    import os

    from . import checksum

    reports: list[ArtifactReport] = []
    for inv in invocations:
        for art in inv.produces:
            matches = sorted(art.root.glob(art.glob))
            if not matches:
                raise RuntimeError(
                    f"artifact {art.glob!r} under {art.root} matched no files"
                )
            for match in matches:
                if not match.is_file():
                    continue
                with open(match, "rb") as fp:
                    size = os.stat(fp.fileno()).st_size
                    csums = checksum.Checksummer(fp, {}).compute(
                        kinds=checksum.SUPPORTED_CHECKSUM_KINDS,
                    )
                reports.append(
                    ArtifactReport(
                        path=match,
                        size=size,
                        checksums=csums,
                    )
                )
    return reports


def format_build_report(report: BuildReport) -> str:
    """Return a TOML-shaped serialization of a build report."""

    lines: list[str] = []
    lines.append("# ruyi build report")
    lines.append(f'recipe_file = "{report.recipe_file}"')
    lines.append(f'project_name = "{report.project_name}"')
    lines.append(f'build_name = "{report.build_name}"')
    lines.append(f"exit_code = {report.exit_code}")
    for inv in report.invocations:
        lines.append("")
        lines.append("[[invocations]]")
        lines.append(f"argv = {list(inv.argv)!r}")
        lines.append(f'cwd = "{inv.cwd}"')
        if inv.env:
            lines.append(f"env = {dict(inv.env)!r}")
    for art in report.artifacts:
        lines.append("")
        lines.append("[[artifacts]]")
        lines.append(f'path = "{art.path}"')
        lines.append(f"size = {art.size}")
        for kind in sorted(art.checksums):
            lines.append(f'{kind} = "{art.checksums[kind]}"')
    return "\n".join(lines) + "\n"
