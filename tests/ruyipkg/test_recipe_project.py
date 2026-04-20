import os
import pathlib

import pytest

from ruyi.ruyipkg.recipe_project import (
    MARKER_FILENAME,
    RecipeProject,
    RecipeProjectError,
    discover_recipe_project,
    safe_join,
)


def _write_marker(root: pathlib.Path, body: str) -> None:
    (root / MARKER_FILENAME).write_text(body)


def test_discover_from_immediate_parent(tmp_path: pathlib.Path) -> None:
    _write_marker(tmp_path, 'format = "v1"\n[project]\nname = "demo"\n')
    recipe = tmp_path / "foo.star"
    recipe.write_text("")

    rp = discover_recipe_project(recipe)
    assert rp.root == tmp_path.resolve()
    assert rp.name == "demo"
    assert rp.output_dir == (tmp_path / "out").resolve()
    assert rp.extra_artifact_roots == ()


def test_discover_walks_up_parents(tmp_path: pathlib.Path) -> None:
    _write_marker(tmp_path, 'format = "v1"\n')
    nested = tmp_path / "a" / "b" / "c"
    nested.mkdir(parents=True)
    recipe = nested / "x.star"
    recipe.write_text("")

    rp = discover_recipe_project(recipe)
    assert rp.root == tmp_path.resolve()
    # Default name falls back to root dir name.
    assert rp.name == tmp_path.name


def test_discover_missing_marker(tmp_path: pathlib.Path) -> None:
    recipe = tmp_path / "x.star"
    recipe.write_text("")
    with pytest.raises(RecipeProjectError, match="no ruyi-build-recipes.toml"):
        discover_recipe_project(recipe)


def test_discover_missing_recipe_file(tmp_path: pathlib.Path) -> None:
    with pytest.raises(RecipeProjectError, match="recipe file not found"):
        discover_recipe_project(tmp_path / "nope.star")


def test_discover_malformed_toml(tmp_path: pathlib.Path) -> None:
    _write_marker(tmp_path, "not = valid = toml")
    recipe = tmp_path / "x.star"
    recipe.write_text("")
    with pytest.raises(RecipeProjectError, match="malformed"):
        discover_recipe_project(recipe)


def test_discover_unsupported_format(tmp_path: pathlib.Path) -> None:
    _write_marker(tmp_path, 'format = "v2"\n')
    recipe = tmp_path / "x.star"
    recipe.write_text("")
    with pytest.raises(RecipeProjectError, match="unsupported or missing 'format'"):
        discover_recipe_project(recipe)


def test_discover_custom_output_dir_and_extras(tmp_path: pathlib.Path) -> None:
    _write_marker(
        tmp_path,
        'format = "v1"\n'
        "[project]\n"
        'name = "demo"\n'
        'output_dir = "dist"\n'
        f'extra_artifact_roots = ["{tmp_path.as_posix()}/scratch"]\n',
    )
    (tmp_path / "scratch").mkdir()
    recipe = tmp_path / "x.star"
    recipe.write_text("")

    rp = discover_recipe_project(recipe)
    assert rp.output_dir == (tmp_path / "dist").resolve()
    assert rp.extra_artifact_roots == ((tmp_path / "scratch").resolve(),)


def test_discover_absolute_output_dir_rejected(tmp_path: pathlib.Path) -> None:
    _write_marker(
        tmp_path,
        'format = "v1"\n[project]\noutput_dir = "/abs"\n',
    )
    recipe = tmp_path / "x.star"
    recipe.write_text("")
    with pytest.raises(
        RecipeProjectError, match="output_dir must be a project-relative"
    ):
        discover_recipe_project(recipe)


def test_discover_traversing_output_dir_rejected(tmp_path: pathlib.Path) -> None:
    _write_marker(
        tmp_path,
        'format = "v1"\n[project]\noutput_dir = "../out"\n',
    )
    recipe = tmp_path / "x.star"
    recipe.write_text("")
    with pytest.raises(RecipeProjectError, match="escapes the project root"):
        discover_recipe_project(recipe)


def test_discover_relative_extra_artifact_root_rejected(tmp_path: pathlib.Path) -> None:
    _write_marker(
        tmp_path,
        'format = "v1"\n[project]\nextra_artifact_roots = ["scratch"]\n',
    )
    recipe = tmp_path / "x.star"
    recipe.write_text("")
    with pytest.raises(RecipeProjectError, match="must be absolute"):
        discover_recipe_project(recipe)


@pytest.mark.skipif(os.name != "posix", reason="symlinks are POSIX-flavored here")
def test_discover_symlink_escape_rejected(tmp_path: pathlib.Path) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    _write_marker(project, 'format = "v1"\n')

    outside = tmp_path / "outside"
    outside.mkdir()
    real_recipe = outside / "x.star"
    real_recipe.write_text("")

    link = project / "x.star"
    link.symlink_to(real_recipe)

    with pytest.raises(RecipeProjectError, match="escapes its project root"):
        discover_recipe_project(link)


def test_safe_join_ok(tmp_path: pathlib.Path) -> None:
    (tmp_path / "lib").mkdir()
    target = tmp_path / "lib" / "docker.star"
    target.write_text("")
    assert safe_join(tmp_path, "lib/docker.star") == target.resolve()


def test_safe_join_rejects_traversal(tmp_path: pathlib.Path) -> None:
    with pytest.raises(RecipeProjectError, match="escapes recipe project root"):
        safe_join(tmp_path, "../evil")


def test_safe_join_rejects_absolute(tmp_path: pathlib.Path) -> None:
    with pytest.raises(RecipeProjectError, match="absolute paths are not allowed"):
        safe_join(tmp_path, "/etc/passwd")


def test_recipe_project_marker_path(tmp_path: pathlib.Path) -> None:
    _write_marker(tmp_path, 'format = "v1"\n')
    recipe = tmp_path / "x.star"
    recipe.write_text("")
    rp = discover_recipe_project(recipe)
    assert isinstance(rp, RecipeProject)
    assert rp.marker_path == tmp_path.resolve() / MARKER_FILENAME


def test_discover_invalid_project_not_table(tmp_path: pathlib.Path) -> None:
    _write_marker(tmp_path, 'format = "v1"\nproject = 1\n')
    recipe = tmp_path / "x.star"
    recipe.write_text("")
    with pytest.raises(RecipeProjectError, match=r"\[project\] must be a table"):
        discover_recipe_project(recipe)


def test_discover_invalid_project_name_empty(tmp_path: pathlib.Path) -> None:
    _write_marker(tmp_path, 'format = "v1"\n[project]\nname = ""\n')
    recipe = tmp_path / "x.star"
    recipe.write_text("")
    with pytest.raises(RecipeProjectError, match="project.name"):
        discover_recipe_project(recipe)


def test_discover_invalid_project_name_non_string(tmp_path: pathlib.Path) -> None:
    _write_marker(tmp_path, 'format = "v1"\n[project]\nname = 123\n')
    recipe = tmp_path / "x.star"
    recipe.write_text("")
    with pytest.raises(RecipeProjectError, match="project.name"):
        discover_recipe_project(recipe)


def test_discover_invalid_extra_artifact_roots_non_list(
    tmp_path: pathlib.Path,
) -> None:
    _write_marker(
        tmp_path,
        'format = "v1"\n[project]\nextra_artifact_roots = "scratch"\n',
    )
    recipe = tmp_path / "x.star"
    recipe.write_text("")
    with pytest.raises(RecipeProjectError, match="extra_artifact_roots"):
        discover_recipe_project(recipe)


def test_discover_invalid_extra_artifact_roots_non_string_item(
    tmp_path: pathlib.Path,
) -> None:
    _write_marker(
        tmp_path,
        'format = "v1"\n[project]\nextra_artifact_roots = ["/ok", 1]\n',
    )
    recipe = tmp_path / "x.star"
    recipe.write_text("")
    with pytest.raises(RecipeProjectError, match="extra_artifact_roots"):
        discover_recipe_project(recipe)
