"""Recipe-project discovery and marker-file parsing.

A *recipe project* is a directory tree with a ``ruyi-build-recipes.toml``
marker at its root. Build recipes (``.star`` files) anywhere beneath the
root may ``load()`` each other via the ``ruyi-build://`` scheme.

This module owns the on-disk representation: discovery of the project
root given a recipe file, parsing the marker, and a realpath-based join
helper used by loaders and the build runner.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import pathlib
import tomllib
from typing import Any


MARKER_FILENAME = "ruyi-build-recipes.toml"
SUPPORTED_FORMATS = frozenset({"v1"})


class RecipeProjectError(RuntimeError):
    """Raised for any ruyi-build-recipes.toml or project-layout problem."""


@dataclass(frozen=True)
class RecipeProject:
    """A discovered recipe project.

    Attributes:
        root: Absolute, realpath-resolved path to the project root.
        name: Human-readable project name from the marker, or the root
            directory name if unspecified.
        output_dir: Project-relative directory for build outputs; absolute
            path computed as ``root / output_dir``.
        extra_artifact_roots: Absolute allow-list for artifact roots
            outside the project tree. Each entry is realpath-resolved.
    """

    root: pathlib.Path
    name: str
    output_dir: pathlib.Path
    extra_artifact_roots: tuple[pathlib.Path, ...] = field(default_factory=tuple)

    @property
    def marker_path(self) -> pathlib.Path:
        return self.root / MARKER_FILENAME


def discover_recipe_project(recipe_file: pathlib.Path) -> RecipeProject:
    """Find the recipe project containing ``recipe_file``.

    Walks the lexical parents of ``recipe_file`` looking for the marker
    file. The realpath of the recipe file must remain within the realpath
    of the project root (defense against symlink escape). Raises
    :class:`RecipeProjectError` if no marker is found or if the realpath
    check fails.
    """

    if not recipe_file.exists():
        raise RecipeProjectError(f"recipe file not found: {recipe_file}")

    recipe_abs = recipe_file.absolute()
    resolved_recipe = recipe_file.resolve(strict=True)

    for candidate in (recipe_abs.parent, *recipe_abs.parents):
        marker = candidate / MARKER_FILENAME
        if marker.is_file():
            root = candidate.resolve(strict=True)
            if not resolved_recipe.is_relative_to(root):
                raise RecipeProjectError(
                    f"recipe file {recipe_file} escapes its project root {root} "
                    f"after realpath resolution"
                )
            return _parse_marker(root, marker)

    raise RecipeProjectError(
        f"no {MARKER_FILENAME} found in any parent of {recipe_file}"
    )


def _parse_marker(root: pathlib.Path, marker: pathlib.Path) -> RecipeProject:
    try:
        with open(marker, "rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise RecipeProjectError(f"malformed {MARKER_FILENAME} at {marker}: {e}") from e

    fmt = data.get("format")
    if fmt not in SUPPORTED_FORMATS:
        raise RecipeProjectError(
            f"{marker}: unsupported or missing 'format' (got {fmt!r}; "
            f"expected one of {sorted(SUPPORTED_FORMATS)})"
        )

    project_section: Any = data.get("project", {})
    if not isinstance(project_section, dict):
        raise RecipeProjectError(f"{marker}: [project] must be a table")

    name = project_section.get("name", root.name)
    if not isinstance(name, str) or not name:
        raise RecipeProjectError(f"{marker}: project.name must be a non-empty string")

    output_dir_raw = project_section.get("output_dir", "out")
    if not isinstance(output_dir_raw, str) or not output_dir_raw:
        raise RecipeProjectError(
            f"{marker}: project.output_dir must be a non-empty string"
        )
    output_dir_rel = pathlib.PurePosixPath(output_dir_raw)
    if output_dir_rel.is_absolute():
        raise RecipeProjectError(
            f"{marker}: project.output_dir must be a project-relative path"
        )
    output_dir = (root / output_dir_rel).resolve()
    if not output_dir.is_relative_to(root):
        raise RecipeProjectError(
            f"{marker}: project.output_dir escapes the project root"
        )

    extra_raw = project_section.get("extra_artifact_roots", [])
    if not isinstance(extra_raw, list) or not all(isinstance(x, str) for x in extra_raw):
        raise RecipeProjectError(
            f"{marker}: project.extra_artifact_roots must be a list of strings"
        )
    extras: list[pathlib.Path] = []
    for entry in extra_raw:
        p = pathlib.Path(entry)
        if not p.is_absolute():
            raise RecipeProjectError(
                f"{marker}: extra_artifact_roots entries must be absolute paths "
                f"(got {entry!r})"
            )
        extras.append(p.resolve())

    return RecipeProject(
        root=root,
        name=name,
        output_dir=output_dir,
        extra_artifact_roots=tuple(extras),
    )


def safe_join(root: pathlib.Path, rel: str) -> pathlib.Path:
    """Join ``rel`` onto ``root`` and verify the result stays inside ``root``.

    Used when resolving ``ruyi-build://``-scheme paths and ``ctx.repo_path``
    calls. Accepts either forward-slash relative paths or plain relative
    paths; absolute inputs are rejected.
    """

    p = pathlib.PurePosixPath(rel)
    if p.is_absolute():
        raise RecipeProjectError(
            f"safe_join: absolute paths are not allowed (got {rel!r})"
        )
    joined = (root / p).resolve()
    root_resolved = root.resolve()
    if not joined.is_relative_to(root_resolved):
        raise RecipeProjectError(
            f"safe_join: {rel!r} escapes recipe project root {root_resolved}"
        )
    return joined
