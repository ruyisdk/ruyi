"""Tests for RuyiBuildRecipeAPI (B5)."""

import pathlib

import pytest

from ruyi.log import RuyiLogger
from ruyi.pluginhost.api import RuyiHostAPI
from ruyi.pluginhost.build_api import RuyiBuildRecipeAPI, ScheduledBuild
from ruyi.pluginhost.ctx import PluginHostContext


def _make_recipe_phctx(
    tmp_path: pathlib.Path,
    ruyi_logger: RuyiLogger,
) -> PluginHostContext:
    plugin_root = tmp_path / "plugins"
    plugin_root.mkdir()
    recipe_root = tmp_path / "recipes_proj"
    recipe_root.mkdir()
    return PluginHostContext.new(
        ruyi_logger,
        plugin_root,
        recipe_project_root=recipe_root,
    )


def _make_plain_phctx(
    tmp_path: pathlib.Path,
    ruyi_logger: RuyiLogger,
) -> PluginHostContext:
    plugin_root = tmp_path / "plugins"
    plugin_root.mkdir()
    return PluginHostContext.new(ruyi_logger, plugin_root)


def test_schedule_build_registers_callable(
    tmp_path: pathlib.Path, ruyi_logger: RuyiLogger
) -> None:
    phctx = _make_recipe_phctx(tmp_path, ruyi_logger)
    recipe_file = tmp_path / "recipes_proj" / "pkg.star"

    api = RuyiBuildRecipeAPI(phctx, recipe_file)

    def build_one(ctx: object) -> None:
        pass

    api.schedule_build(build_one)

    registry = phctx.scheduled_builds_for(recipe_file)
    assert len(registry) == 1
    sb = registry[0]
    assert isinstance(sb, ScheduledBuild)
    assert sb.name == "build_one"
    assert sb.fn is build_one
    assert sb.recipe_file == recipe_file


def test_schedule_build_explicit_name(
    tmp_path: pathlib.Path, ruyi_logger: RuyiLogger
) -> None:
    phctx = _make_recipe_phctx(tmp_path, ruyi_logger)
    recipe_file = tmp_path / "recipes_proj" / "pkg.star"
    api = RuyiBuildRecipeAPI(phctx, recipe_file)

    api.schedule_build(lambda ctx: None, name="custom")

    registry = phctx.scheduled_builds_for(recipe_file)
    assert [sb.name for sb in registry] == ["custom"]


def test_schedule_build_rejects_non_callable(
    tmp_path: pathlib.Path, ruyi_logger: RuyiLogger
) -> None:
    phctx = _make_recipe_phctx(tmp_path, ruyi_logger)
    recipe_file = tmp_path / "recipes_proj" / "pkg.star"
    api = RuyiBuildRecipeAPI(phctx, recipe_file)

    with pytest.raises(RuntimeError, match="expected a callable"):
        api.schedule_build("not a function")  # type: ignore[arg-type]


def test_schedule_build_accepts_lambda(
    tmp_path: pathlib.Path, ruyi_logger: RuyiLogger
) -> None:
    phctx = _make_recipe_phctx(tmp_path, ruyi_logger)
    recipe_file = tmp_path / "recipes_proj" / "pkg.star"
    api = RuyiBuildRecipeAPI(phctx, recipe_file)

    api.schedule_build(lambda ctx: None)
    assert phctx.scheduled_builds_for(recipe_file)[0].name == "<lambda>"


def test_schedule_build_rejects_duplicate_name(
    tmp_path: pathlib.Path, ruyi_logger: RuyiLogger
) -> None:
    phctx = _make_recipe_phctx(tmp_path, ruyi_logger)
    recipe_file = tmp_path / "recipes_proj" / "pkg.star"
    api = RuyiBuildRecipeAPI(phctx, recipe_file)

    api.schedule_build(lambda ctx: None, name="dup")
    with pytest.raises(RuntimeError, match="duplicate build name"):
        api.schedule_build(lambda ctx: None, name="dup")


def test_recipe_phctx_has_build_recipe_capability(
    tmp_path: pathlib.Path, ruyi_logger: RuyiLogger
) -> None:
    phctx = _make_recipe_phctx(tmp_path, ruyi_logger)
    assert "build-recipe-v1" in phctx.capabilities
    # Recipes must go through ctx.subprocess; raw subprocess is denied.
    assert "call-subprocess-v1" not in phctx.capabilities


def test_plain_phctx_does_not_have_build_recipe_capability(
    tmp_path: pathlib.Path, ruyi_logger: RuyiLogger
) -> None:
    phctx = _make_plain_phctx(tmp_path, ruyi_logger)
    assert "build-recipe-v1" not in phctx.capabilities
    assert "call-subprocess-v1" in phctx.capabilities


def test_build_namespace_gated_on_capability(
    tmp_path: pathlib.Path, ruyi_logger: RuyiLogger
) -> None:
    phctx = _make_plain_phctx(tmp_path, ruyi_logger)
    host_api = RuyiHostAPI(
        phctx,
        this_file=tmp_path / "unused.star",
        this_plugin_dir=tmp_path,
        allow_host_fs_access=False,
    )
    with pytest.raises(
        RuntimeError, match="only available when loading a build recipe"
    ):
        _ = host_api.build


def test_build_namespace_available_in_recipe_context(
    tmp_path: pathlib.Path, ruyi_logger: RuyiLogger
) -> None:
    phctx = _make_recipe_phctx(tmp_path, ruyi_logger)
    recipe_file = tmp_path / "recipes_proj" / "pkg.star"
    host_api = RuyiHostAPI(
        phctx,
        this_file=recipe_file,
        this_plugin_dir=tmp_path / "recipes_proj",
        allow_host_fs_access=False,
    )
    build = host_api.build
    assert isinstance(build, RuyiBuildRecipeAPI)


def test_call_subprocess_rejected_in_recipe_context(
    tmp_path: pathlib.Path, ruyi_logger: RuyiLogger
) -> None:
    phctx = _make_recipe_phctx(tmp_path, ruyi_logger)
    recipe_file = tmp_path / "recipes_proj" / "pkg.star"
    host_api = RuyiHostAPI(
        phctx,
        this_file=recipe_file,
        this_plugin_dir=tmp_path / "recipes_proj",
        allow_host_fs_access=False,
    )
    with pytest.raises(RuntimeError, match="call_subprocess_argv is not available"):
        host_api.call_subprocess_argv(["/bin/true"])
