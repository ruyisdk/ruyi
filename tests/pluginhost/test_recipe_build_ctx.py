"""Tests for RecipeBuildCtx and plan records (B6)."""

import pathlib

import pytest

from ruyi.pluginhost.build_api import (
    Artifact,
    Invocation,
    RecipeBuildCtx,
)
from ruyi.ruyipkg.recipe_project import RecipeProject


def _make_project(tmp_path: pathlib.Path) -> RecipeProject:
    root = tmp_path.resolve()
    (root / "out").mkdir(exist_ok=True)
    return RecipeProject(
        root=root,
        name="test",
        output_dir=(root / "out").resolve(),
        extra_artifact_roots=((tmp_path / "scratch").resolve(),),
    )


def _make_ctx(
    tmp_path: pathlib.Path,
    user_vars: dict[str, str] | None = None,
) -> RecipeBuildCtx:
    (tmp_path / "scratch").mkdir(exist_ok=True)
    project = _make_project(tmp_path)
    recipe = project.root / "recipes" / "pkg.star"
    recipe.parent.mkdir(parents=True, exist_ok=True)
    recipe.write_text("")
    return RecipeBuildCtx(
        project=project,
        name="b1",
        recipe_file=recipe,
        user_vars=user_vars or {},
    )


def test_ctx_identity_fields(tmp_path: pathlib.Path) -> None:
    ctx = _make_ctx(tmp_path)
    assert ctx.name == "b1"
    assert ctx.recipe_file.endswith("pkg.star")
    assert ctx.repo_root == str(tmp_path.resolve())


def test_ctx_repo_path_safe_join(tmp_path: pathlib.Path) -> None:
    ctx = _make_ctx(tmp_path)
    (tmp_path / "src").mkdir()
    assert ctx.repo_path("src") == str((tmp_path / "src").resolve())


def test_ctx_repo_path_traversal_rejected(tmp_path: pathlib.Path) -> None:
    ctx = _make_ctx(tmp_path)
    with pytest.raises(RuntimeError, match="escapes recipe project root"):
        ctx.repo_path("../evil")


def test_ctx_var_returns_provided(tmp_path: pathlib.Path) -> None:
    ctx = _make_ctx(tmp_path, user_vars={"arch": "riscv64"})
    assert ctx.var("arch") == "riscv64"


def test_ctx_var_default(tmp_path: pathlib.Path) -> None:
    ctx = _make_ctx(tmp_path)
    assert ctx.var("arch", default="amd64") == "amd64"


def test_ctx_var_missing_no_default_errors(tmp_path: pathlib.Path) -> None:
    ctx = _make_ctx(tmp_path)
    with pytest.raises(RuntimeError, match="no value provided"):
        ctx.var("arch")


def test_ctx_var_non_string_default_rejected(tmp_path: pathlib.Path) -> None:
    ctx = _make_ctx(tmp_path)
    with pytest.raises(RuntimeError, match="must be a string"):
        ctx.var("arch", default=42)


def test_ctx_subprocess_returns_plan(tmp_path: pathlib.Path) -> None:
    ctx = _make_ctx(tmp_path)
    inv = ctx.subprocess(
        argv=["/bin/true", "hello"],
        env={"FOO": "bar"},
    )
    assert isinstance(inv, Invocation)
    assert inv.argv == ("/bin/true", "hello")
    assert inv.cwd == tmp_path.resolve()
    assert inv.env == {"FOO": "bar"}
    assert inv.produces == ()


def test_ctx_subprocess_rejects_empty_argv(tmp_path: pathlib.Path) -> None:
    ctx = _make_ctx(tmp_path)
    with pytest.raises(RuntimeError, match="argv must be non-empty"):
        ctx.subprocess(argv=[])


def test_ctx_subprocess_rejects_non_string_argv(tmp_path: pathlib.Path) -> None:
    ctx = _make_ctx(tmp_path)
    with pytest.raises(RuntimeError, match="argv entries must be strings"):
        ctx.subprocess(argv=["/bin/true", 1])  # type: ignore[list-item]


def test_ctx_subprocess_rejects_non_artifact_produces(tmp_path: pathlib.Path) -> None:
    ctx = _make_ctx(tmp_path)
    with pytest.raises(RuntimeError, match="produces entries must be Artifact"):
        ctx.subprocess(argv=["/bin/true"], produces=["foo.tar"])  # type: ignore[list-item]


def test_ctx_subprocess_carries_produces(tmp_path: pathlib.Path) -> None:
    ctx = _make_ctx(tmp_path)
    a = ctx.artifact("*.tar.zst")
    inv = ctx.subprocess(argv=["/bin/true"], produces=[a])
    assert inv.produces == (a,)


def test_ctx_artifact_defaults_to_output_dir(tmp_path: pathlib.Path) -> None:
    ctx = _make_ctx(tmp_path)
    a = ctx.artifact("*.tar.zst")
    assert isinstance(a, Artifact)
    assert a.glob == "*.tar.zst"
    assert a.root == (tmp_path / "out").resolve()


def test_ctx_artifact_relative_root_resolved_under_project(
    tmp_path: pathlib.Path,
) -> None:
    ctx = _make_ctx(tmp_path)
    (tmp_path / "dist").mkdir()
    a = ctx.artifact("*.tar.zst", root="dist")
    assert a.root == (tmp_path / "dist").resolve()


def test_ctx_artifact_absolute_root_must_be_in_allowlist(
    tmp_path: pathlib.Path,
) -> None:
    ctx = _make_ctx(tmp_path)
    a = ctx.artifact("*.tar.zst", root=str(tmp_path / "scratch"))
    assert a.root == (tmp_path / "scratch").resolve()


def test_ctx_artifact_absolute_root_outside_allowlist_rejected(
    tmp_path: pathlib.Path,
) -> None:
    ctx = _make_ctx(tmp_path)
    with pytest.raises(RuntimeError, match="not in extra_artifact_roots"):
        ctx.artifact("*.tar.zst", root="/etc")


def test_ctx_artifact_relative_traversal_rejected(tmp_path: pathlib.Path) -> None:
    ctx = _make_ctx(tmp_path)
    with pytest.raises(RuntimeError, match="escapes recipe project root"):
        ctx.artifact("*.tar.zst", root="../evil")


def test_ctx_artifact_empty_glob_rejected(tmp_path: pathlib.Path) -> None:
    ctx = _make_ctx(tmp_path)
    with pytest.raises(RuntimeError, match="glob must be a non-empty"):
        ctx.artifact("")
