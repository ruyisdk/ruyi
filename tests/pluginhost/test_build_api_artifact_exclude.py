from __future__ import annotations

import pathlib

import pytest

from ruyi.pluginhost.build_api import Artifact, RecipeBuildCtx
from ruyi.ruyipkg.recipe_project import RecipeProject


def _ctx(tmp_path: pathlib.Path) -> RecipeBuildCtx:
    project = RecipeProject(
        root=tmp_path,
        name="proj",
        output_dir=tmp_path / "out",
        extra_artifact_roots=(),
    )
    return RecipeBuildCtx(
        project=project,
        name="b",
        recipe_file=tmp_path / "pkg.star",
        user_vars={},
    )


def test_artifact_default_exclude_is_empty(tmp_path: pathlib.Path) -> None:
    art = _ctx(tmp_path).artifact("*.tar.gz")
    assert isinstance(art, Artifact)
    assert art.exclude == ()


def test_artifact_stores_exclude_patterns(tmp_path: pathlib.Path) -> None:
    art = _ctx(tmp_path).artifact("*.tar.gz", exclude=["tests/**", "*.debug"])
    assert art.exclude == ("tests/**", "*.debug")


def test_artifact_rejects_non_list_exclude(tmp_path: pathlib.Path) -> None:
    with pytest.raises(RuntimeError):
        _ctx(tmp_path).artifact("*.tar.gz", exclude="oops")  # type: ignore[arg-type]


def test_artifact_rejects_non_str_exclude_entry(tmp_path: pathlib.Path) -> None:
    with pytest.raises(RuntimeError):
        _ctx(tmp_path).artifact("*.tar.gz", exclude=[1])  # type: ignore[list-item]
