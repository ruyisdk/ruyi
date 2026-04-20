"""CLI integration tests for `ruyi admin build-package` (B8)."""

from __future__ import annotations

import pathlib

from tests.fixtures import IntegrationTestHarness


def _setup_project(tmp_path: pathlib.Path, recipe_body: str) -> pathlib.Path:
    proj = tmp_path / "recipes-proj"
    proj.mkdir()
    (proj / "ruyi-build-recipes.toml").write_text(
        'format = "v1"\n[project]\nname = "integ"\n'
    )
    (proj / "out").mkdir()
    recipe = proj / "pkg.star"
    recipe.write_text(recipe_body)
    return recipe


def test_admin_build_package_dry_run(
    tmp_path: pathlib.Path,
    ruyi_cli_runner: IntegrationTestHarness,
) -> None:
    recipe = _setup_project(
        tmp_path,
        "RUYI = ruyi_plugin_rev(1)\n"
        "def build_it(ctx):\n"
        "    return ctx.subprocess(argv = ['/bin/true'])\n"
        "RUYI.build.schedule_build(build_it)\n",
    )

    result = ruyi_cli_runner("admin", "build-package", "--dry-run", str(recipe))
    assert result.exit_code == 0, result.stderr
    assert "build_it" in result.stdout


def test_admin_build_package_executes(
    tmp_path: pathlib.Path,
    ruyi_cli_runner: IntegrationTestHarness,
) -> None:
    recipe = _setup_project(
        tmp_path,
        "RUYI = ruyi_plugin_rev(1)\n"
        "def build_it(ctx):\n"
        "    return ctx.subprocess(argv = ['/bin/true'])\n"
        "RUYI.build.schedule_build(build_it)\n",
    )
    result = ruyi_cli_runner("admin", "build-package", str(recipe))
    assert result.exit_code == 0, result.stderr


def test_admin_build_package_var_flag(
    tmp_path: pathlib.Path,
    ruyi_cli_runner: IntegrationTestHarness,
) -> None:
    recipe = _setup_project(
        tmp_path,
        "RUYI = ruyi_plugin_rev(1)\n"
        "def build_it(ctx):\n"
        "    return ctx.subprocess(argv = ['/bin/echo', ctx.var('arch')])\n"
        "RUYI.build.schedule_build(build_it)\n",
    )
    result = ruyi_cli_runner(
        "admin",
        "build-package",
        "--dry-run",
        "-v",
        "arch=riscv64",
        str(recipe),
    )
    assert result.exit_code == 0, result.stderr
    assert "riscv64" in result.stdout


def test_admin_build_package_invalid_var(
    tmp_path: pathlib.Path,
    ruyi_cli_runner: IntegrationTestHarness,
) -> None:
    recipe = _setup_project(
        tmp_path,
        "RUYI = ruyi_plugin_rev(1)\n"
        "def build_it(ctx):\n"
        "    return ctx.subprocess(argv = ['/bin/true'])\n"
        "RUYI.build.schedule_build(build_it)\n",
    )
    result = ruyi_cli_runner(
        "admin",
        "build-package",
        "--dry-run",
        "-v",
        "no_equals_here",
        str(recipe),
    )
    assert result.exit_code == 1


def test_admin_build_package_build_failure_exits_nonzero(
    tmp_path: pathlib.Path,
    ruyi_cli_runner: IntegrationTestHarness,
) -> None:
    recipe = _setup_project(
        tmp_path,
        "RUYI = ruyi_plugin_rev(1)\n"
        "def build_it(ctx):\n"
        "    return ctx.subprocess(argv = ['/bin/false'])\n"
        "RUYI.build.schedule_build(build_it)\n",
    )
    result = ruyi_cli_runner("admin", "build-package", str(recipe))
    assert result.exit_code != 0
