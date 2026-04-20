"""Tests for the recipe build runner (B7)."""

from __future__ import annotations

import pathlib

import pytest

from ruyi.log import RuyiLogger
from ruyi.ruyipkg.build_runner import (
    BuildFailure,
    format_build_report,
    run_recipe,
)


def _make_project(tmp_path: pathlib.Path, recipe_body: str) -> pathlib.Path:
    (tmp_path / "ruyi-build-recipes.toml").write_text(
        'format = "v1"\n[project]\nname = "testproj"\n'
    )
    (tmp_path / "out").mkdir(exist_ok=True)
    recipe_dir = tmp_path / "recipes"
    recipe_dir.mkdir(exist_ok=True)
    recipe = recipe_dir / "pkg.star"
    recipe.write_text(recipe_body)
    return recipe


def test_run_recipe_dry_run(tmp_path: pathlib.Path, ruyi_logger: RuyiLogger) -> None:
    recipe = _make_project(
        tmp_path,
        "RUYI = ruyi_plugin_rev(1)\n"
        "def build_it(ctx):\n"
        "    return ctx.subprocess(argv = ['/bin/true', 'hi'])\n"
        "\n"
        "RUYI.build.schedule_build(build_it)\n",
    )

    reports = run_recipe(ruyi_logger, recipe, dry_run=True)
    assert len(reports) == 1
    r = reports[0]
    assert r.build_name == "build_it"
    assert r.invocations[0].argv == ("/bin/true", "hi")
    assert r.exit_code == 0
    assert r.artifacts == ()


def test_run_recipe_no_scheduled_builds_errors(
    tmp_path: pathlib.Path, ruyi_logger: RuyiLogger
) -> None:
    recipe = _make_project(tmp_path, "RUYI = ruyi_plugin_rev(1)\n")
    with pytest.raises(RuntimeError, match="scheduled no builds"):
        run_recipe(ruyi_logger, recipe, dry_run=True)


def test_run_recipe_name_filter_selects(
    tmp_path: pathlib.Path, ruyi_logger: RuyiLogger
) -> None:
    recipe = _make_project(
        tmp_path,
        "RUYI = ruyi_plugin_rev(1)\n"
        "def build_a(ctx):\n"
        "    return ctx.subprocess(argv = ['/bin/true', 'a'])\n"
        "def build_b(ctx):\n"
        "    return ctx.subprocess(argv = ['/bin/true', 'b'])\n"
        "\n"
        "RUYI.build.schedule_build(build_a)\n"
        "RUYI.build.schedule_build(build_b)\n",
    )
    reports = run_recipe(ruyi_logger, recipe, dry_run=True, selected_names=["build_b"])
    assert [r.build_name for r in reports] == ["build_b"]


def test_run_recipe_name_filter_missing_errors(
    tmp_path: pathlib.Path, ruyi_logger: RuyiLogger
) -> None:
    recipe = _make_project(
        tmp_path,
        "RUYI = ruyi_plugin_rev(1)\n"
        "def build_a(ctx):\n"
        "    return ctx.subprocess(argv = ['/bin/true'])\n"
        "RUYI.build.schedule_build(build_a)\n",
    )
    with pytest.raises(RuntimeError, match="does not define the requested"):
        run_recipe(ruyi_logger, recipe, dry_run=True, selected_names=["nope"])


def test_run_recipe_user_vars(tmp_path: pathlib.Path, ruyi_logger: RuyiLogger) -> None:
    recipe = _make_project(
        tmp_path,
        "RUYI = ruyi_plugin_rev(1)\n"
        "def build_it(ctx):\n"
        "    arch = ctx.var('arch')\n"
        "    return ctx.subprocess(argv = ['/bin/echo', arch])\n"
        "RUYI.build.schedule_build(build_it)\n",
    )
    reports = run_recipe(
        ruyi_logger,
        recipe,
        dry_run=True,
        user_vars={"arch": "riscv64"},
    )
    assert reports[0].invocations[0].argv == ("/bin/echo", "riscv64")


def test_run_recipe_executes_and_collects_artifacts(
    tmp_path: pathlib.Path, ruyi_logger: RuyiLogger
) -> None:
    out = tmp_path / "out"
    out.mkdir(exist_ok=True)
    artifact = out / "pkg-1.0.tar.zst"
    artifact.write_bytes(b"dummy")

    recipe = _make_project(
        tmp_path,
        "RUYI = ruyi_plugin_rev(1)\n"
        "def build_it(ctx):\n"
        "    return ctx.subprocess(\n"
        "        argv = ['/bin/true'],\n"
        "        produces = [ctx.artifact(glob = 'pkg-*.tar.zst')],\n"
        "    )\n"
        "RUYI.build.schedule_build(build_it)\n",
    )

    reports = run_recipe(ruyi_logger, recipe)
    assert len(reports) == 1
    r = reports[0]
    assert r.exit_code == 0
    assert len(r.artifacts) == 1
    ar = r.artifacts[0]
    assert ar.path == artifact
    assert ar.size == 5
    assert len(ar.checksums["sha256"]) == 64
    assert len(ar.checksums["sha512"]) == 128


def test_run_recipe_missing_artifact_fails(
    tmp_path: pathlib.Path, ruyi_logger: RuyiLogger
) -> None:
    recipe = _make_project(
        tmp_path,
        "RUYI = ruyi_plugin_rev(1)\n"
        "def build_it(ctx):\n"
        "    return ctx.subprocess(\n"
        "        argv = ['/bin/true'],\n"
        "        produces = [ctx.artifact(glob = 'nope-*.tar')],\n"
        "    )\n"
        "RUYI.build.schedule_build(build_it)\n",
    )
    with pytest.raises(RuntimeError, match="matched no files"):
        run_recipe(ruyi_logger, recipe)


def test_run_recipe_non_zero_exit_raises_build_failure(
    tmp_path: pathlib.Path, ruyi_logger: RuyiLogger
) -> None:
    recipe = _make_project(
        tmp_path,
        "RUYI = ruyi_plugin_rev(1)\n"
        "def build_it(ctx):\n"
        "    return ctx.subprocess(argv = ['/bin/false'])\n"
        "RUYI.build.schedule_build(build_it)\n",
    )
    with pytest.raises(BuildFailure) as excinfo:
        run_recipe(ruyi_logger, recipe)
    assert excinfo.value.exit_code != 0
    assert excinfo.value.build_name == "build_it"


def test_run_recipe_supports_ruyi_build_load(
    tmp_path: pathlib.Path, ruyi_logger: RuyiLogger
) -> None:
    (tmp_path / "ruyi-build-recipes.toml").write_text('format = "v1"\n')
    (tmp_path / "out").mkdir(exist_ok=True)
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "common.star").write_text("GREETING = 'hi from lib'\n")

    recipe = tmp_path / "recipes" / "pkg.star"
    recipe.parent.mkdir()
    recipe.write_text(
        "RUYI = ruyi_plugin_rev(1)\n"
        "load('ruyi-build://lib/common.star', 'GREETING')\n"
        "def build_it(ctx):\n"
        "    return ctx.subprocess(argv = ['/bin/echo', GREETING])\n"
        "RUYI.build.schedule_build(build_it)\n"
    )

    reports = run_recipe(ruyi_logger, recipe, dry_run=True)
    assert reports[0].invocations[0].argv == ("/bin/echo", "hi from lib")


def test_format_build_report_is_reasonable(
    tmp_path: pathlib.Path, ruyi_logger: RuyiLogger
) -> None:
    recipe = _make_project(
        tmp_path,
        "RUYI = ruyi_plugin_rev(1)\n"
        "def build_it(ctx):\n"
        "    return ctx.subprocess(argv = ['/bin/true'])\n"
        "RUYI.build.schedule_build(build_it)\n",
    )
    reports = run_recipe(ruyi_logger, recipe, dry_run=True)
    text = format_build_report(reports[0])
    assert 'build_name = "build_it"' in text
    assert "[[invocations]]" in text


def test_format_build_report_includes_artifacts(
    tmp_path: pathlib.Path, ruyi_logger: RuyiLogger
) -> None:
    out = tmp_path / "out"
    out.mkdir(exist_ok=True)
    (out / "pkg-1.0.tar.zst").write_bytes(b"dummy")

    recipe = _make_project(
        tmp_path,
        "RUYI = ruyi_plugin_rev(1)\n"
        "def build_it(ctx):\n"
        "    return ctx.subprocess(\n"
        "        argv = ['/bin/true'],\n"
        "        produces = [ctx.artifact(glob = 'pkg-*.tar.zst')],\n"
        "    )\n"
        "RUYI.build.schedule_build(build_it)\n",
    )
    reports = run_recipe(ruyi_logger, recipe)
    text = format_build_report(reports[0])
    ar = reports[0].artifacts[0]
    assert "[[artifacts]]" in text
    assert f'path = "{ar.path}"' in text
    assert f"size = {ar.size}" in text
    assert f'sha256 = "{ar.checksums["sha256"]}"' in text
    assert f'sha512 = "{ar.checksums["sha512"]}"' in text


def test_run_recipe_rejects_non_invocation_return(
    tmp_path: pathlib.Path, ruyi_logger: RuyiLogger
) -> None:
    recipe = _make_project(
        tmp_path,
        "RUYI = ruyi_plugin_rev(1)\n"
        "def build_it(ctx):\n"
        "    return 'not-an-invocation'\n"
        "RUYI.build.schedule_build(build_it)\n",
    )
    with pytest.raises(RuntimeError, match="expected Invocation"):
        run_recipe(ruyi_logger, recipe, dry_run=True)


def test_run_recipe_rejects_list_with_non_invocation(
    tmp_path: pathlib.Path, ruyi_logger: RuyiLogger
) -> None:
    recipe = _make_project(
        tmp_path,
        "RUYI = ruyi_plugin_rev(1)\n"
        "def build_it(ctx):\n"
        "    return [ctx.subprocess(argv = ['/bin/true']), 42]\n"
        "RUYI.build.schedule_build(build_it)\n",
    )
    with pytest.raises(RuntimeError, match="expected Invocation"):
        run_recipe(ruyi_logger, recipe, dry_run=True)


def test_run_recipe_rejects_empty_list(
    tmp_path: pathlib.Path, ruyi_logger: RuyiLogger
) -> None:
    recipe = _make_project(
        tmp_path,
        "RUYI = ruyi_plugin_rev(1)\n"
        "def build_it(ctx):\n"
        "    return []\n"
        "RUYI.build.schedule_build(build_it)\n",
    )
    with pytest.raises(RuntimeError, match="empty list"):
        run_recipe(ruyi_logger, recipe, dry_run=True)


def test_run_recipe_output_dir_override(
    tmp_path: pathlib.Path, ruyi_logger: RuyiLogger
) -> None:
    override_out = tmp_path / "override_out"
    override_out.mkdir()
    (override_out / "overridden.tar.zst").write_bytes(b"ok")

    recipe = _make_project(
        tmp_path,
        "RUYI = ruyi_plugin_rev(1)\n"
        "def build_it(ctx):\n"
        "    return ctx.subprocess(\n"
        "        argv = ['/bin/true'],\n"
        "        produces = [ctx.artifact(glob = '*.tar.zst')],\n"
        "    )\n"
        "RUYI.build.schedule_build(build_it)\n",
    )
    reports = run_recipe(ruyi_logger, recipe, output_dir_override=override_out)
    assert len(reports) == 1
    assert len(reports[0].artifacts) == 1
    assert (
        reports[0].artifacts[0].path == (override_out / "overridden.tar.zst").resolve()
    )
