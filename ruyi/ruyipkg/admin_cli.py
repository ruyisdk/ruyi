import argparse
import pathlib
from typing import TYPE_CHECKING, cast

from ..cli.cmd import AdminCommand
from ..i18n import _

if TYPE_CHECKING:
    from ..cli.completion import ArgumentParser
    from ..config import GlobalConfig


class AdminChecksumCommand(
    AdminCommand,
    cmd="checksum",
    help=_("Generate a checksum section for a manifest file for the distfiles given"),
):
    @classmethod
    def configure_args(cls, gc: "GlobalConfig", p: "ArgumentParser") -> None:
        p.add_argument(
            "--format",
            "-f",
            type=str,
            choices=["toml"],
            default="toml",
            help=_("Format of checksum section to generate in"),
        )
        p.add_argument(
            "--restrict",
            type=str,
            default="",
            help=_(
                "the 'restrict' field to use for all mentioned distfiles, separated with comma"
            ),
        )
        p.add_argument(
            "file",
            type=str,
            nargs="+",
            help=_("Path to the distfile(s) to checksum"),
        )

    @classmethod
    def main(cls, cfg: "GlobalConfig", args: argparse.Namespace) -> int:
        from .admin_checksum import do_admin_checksum

        logger = cfg.logger
        files = args.file
        format = args.format
        restrict_str = cast(str, args.restrict)
        restrict = restrict_str.split(",") if restrict_str else []

        return do_admin_checksum(logger, files, format, restrict)


class AdminFormatManifestCommand(
    AdminCommand,
    cmd="format-manifest",
    help=_("Format the given package manifests into canonical TOML representation"),
):
    @classmethod
    def configure_args(cls, gc: "GlobalConfig", p: "ArgumentParser") -> None:
        p.add_argument(
            "file",
            type=str,
            nargs="+",
            help=_("Path to the distfile(s) to generate manifest for"),
        )

    @classmethod
    def main(cls, cfg: "GlobalConfig", args: argparse.Namespace) -> int:
        from .canonical_dump import dumps_canonical_package_manifest_toml
        from .pkg_manifest import PackageManifest

        files = args.file

        for f in files:
            p = pathlib.Path(f)
            pm = PackageManifest.load_from_path(p)
            d = dumps_canonical_package_manifest_toml(pm)

            dest_path = p.with_suffix(".toml")
            with open(dest_path, "w", encoding="utf-8") as fp:
                fp.write(d)

        return 0


class AdminBuildPackageCommand(
    AdminCommand,
    cmd="build-package",
    help=_("Build a package from a recipe file"),
):
    @classmethod
    def configure_args(cls, gc: "GlobalConfig", p: "ArgumentParser") -> None:
        p.add_argument(
            "recipe_file",
            type=str,
            help=_("Path to the recipe .star file"),
        )
        p.add_argument(
            "-v",
            "--var",
            action="append",
            default=[],
            metavar="KEY=VALUE",
            help=_("Set a user variable for the recipe (repeatable)"),
        )
        p.add_argument(
            "-n",
            "--name",
            action="append",
            default=[],
            metavar="NAME",
            help=_(
                "Select a specific scheduled build by name (repeatable); "
                "by default all scheduled builds are executed"
            ),
        )
        p.add_argument(
            "--dry-run",
            action="store_true",
            help=_("Print the build plan without executing it"),
        )
        p.add_argument(
            "--output-dir",
            type=str,
            default=None,
            help=_("Override the recipe project's output directory"),
        )

    @classmethod
    def main(cls, cfg: "GlobalConfig", args: argparse.Namespace) -> int:
        from .build_runner import (
            BuildFailure,
            format_build_report,
            run_recipe,
        )

        logger = cfg.logger
        recipe_file = pathlib.Path(cast(str, args.recipe_file))
        var_strs = cast("list[str]", args.var)
        selected_names = cast("list[str]", args.name) or None
        dry_run = cast(bool, args.dry_run)
        output_dir_raw = cast("str | None", args.output_dir)
        output_dir = (
            pathlib.Path(output_dir_raw) if output_dir_raw is not None else None
        )

        user_vars: dict[str, str] = {}
        for v in var_strs:
            if "=" not in v:
                logger.F(
                    _("invalid --var spec {spec!r}: expected KEY=VALUE").format(
                        spec=v,
                    )
                )
                return 1
            k, _sep, val = v.partition("=")
            if not k:
                logger.F(_("invalid --var spec {spec!r}: empty key").format(spec=v))
                return 1
            user_vars[k] = val

        try:
            reports = run_recipe(
                logger,
                recipe_file,
                user_vars=user_vars,
                selected_names=selected_names,
                dry_run=dry_run,
                output_dir_override=output_dir,
            )
        except BuildFailure as e:
            logger.F(str(e))
            return e.exit_code or 1
        except (RuntimeError, FileNotFoundError) as e:
            logger.F(str(e))
            return 1

        for r in reports:
            logger.I(
                _("build {name!r} completed: {n} artifact(s)").format(
                    name=r.build_name,
                    n=len(r.artifacts),
                )
            )
            print(format_build_report(r))

        return 0
