import argparse
import pathlib
from typing import TYPE_CHECKING, cast

from ..cli.cmd import AdminCommand

if TYPE_CHECKING:
    from ..cli.completion import ArgumentParser
    from ..config import GlobalConfig


class AdminChecksumCommand(
    AdminCommand,
    cmd="checksum",
    help="Generate a checksum section for a manifest file for the distfiles given",
):
    @classmethod
    def configure_args(cls, gc: "GlobalConfig", p: "ArgumentParser") -> None:
        p.add_argument(
            "--format",
            "-f",
            type=str,
            choices=["toml"],
            default="toml",
            help="Format of checksum section to generate in",
        )
        p.add_argument(
            "--restrict",
            type=str,
            default="",
            help="the 'restrict' field to use for all mentioned distfiles, separated with comma",
        )
        p.add_argument(
            "file",
            type=str,
            nargs="+",
            help="Path to the distfile(s) to checksum",
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
    help="Format the given package manifests into canonical TOML representation",
):
    @classmethod
    def configure_args(cls, gc: "GlobalConfig", p: "ArgumentParser") -> None:
        p.add_argument(
            "file",
            type=str,
            nargs="+",
            help="Path to the distfile(s) to generate manifest for",
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
