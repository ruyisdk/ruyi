import argparse
import os.path

from ..cli.cmd import RootCommand
from ..config import GlobalConfig
from .atom import Atom
from .distfile import Distfile
from .host import canonicalize_host_str, get_native_host
from .install import do_install_atoms, do_uninstall_atoms
from .unpack import ensure_unpack_cmd_for_method


class ExtractCommand(
    RootCommand,
    cmd="extract",
    help="Fetch package(s) then extract to current directory",
):
    @classmethod
    def configure_args(cls, gc: GlobalConfig, p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "atom",
            type=str,
            nargs="+",
            help="Specifier (atom) of the package(s) to extract",
        )
        p.add_argument(
            "--host",
            type=str,
            default=get_native_host(),
            help="Override the host architecture (normally not needed)",
        )

    @classmethod
    def main(cls, cfg: GlobalConfig, args: argparse.Namespace) -> int:
        logger = cfg.logger
        host = args.host
        atom_strs: set[str] = set(args.atom)
        logger.D(f"about to extract for host {host}: {atom_strs}")

        mr = cfg.repo

        for a_str in atom_strs:
            a = Atom.parse(a_str)
            pm = a.match_in_repo(mr, cfg.include_prereleases)
            if pm is None:
                logger.F(f"atom {a_str} matches no package in the repository")
                return 1
            pkg_name = pm.name_for_installation

            sv = pm.service_level
            if sv.has_known_issues:
                logger.W("package has known issue(s)")
                for s in sv.render_known_issues(pm.repo.messages, cfg.lang_code):
                    logger.I(s)

            bm = pm.binary_metadata
            sm = pm.source_metadata
            if bm is None and sm is None:
                logger.F(f"don't know how to extract package [green]{pkg_name}[/]")
                return 2

            if bm is not None and sm is not None:
                logger.F(
                    f"cannot handle package [green]{pkg_name}[/]: package is both binary and source"
                )
                return 2

            distfiles_for_host: list[str] | None = None
            if bm is not None:
                distfiles_for_host = bm.get_distfile_names_for_host(host)
            elif sm is not None:
                distfiles_for_host = sm.get_distfile_names_for_host(host)

            if not distfiles_for_host:
                logger.F(
                    f"package [green]{pkg_name}[/] declares no distfile for host {host}"
                )
                return 2

            dfs = pm.distfiles()

            for df_name in distfiles_for_host:
                df_decl = dfs[df_name]
                urls = mr.get_distfile_urls(df_decl)
                dest = os.path.join(cfg.ensure_distfiles_dir(), df_name)
                ensure_unpack_cmd_for_method(logger, df_decl.unpack_method)
                df = Distfile(urls, dest, df_decl, mr)
                df.ensure(logger)

                logger.I(
                    f"extracting [green]{df_name}[/] for package [green]{pkg_name}[/]"
                )
                # unpack into CWD
                df.unpack(None, logger)

            logger.I(
                f"package [green]{pkg_name}[/] extracted to current working directory"
            )

        return 0


class InstallCommand(
    RootCommand,
    cmd="install",
    aliases=["i"],
    help="Install package from configured repository",
):
    @classmethod
    def configure_args(cls, gc: GlobalConfig, p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "atom",
            type=str,
            nargs="+",
            help="Specifier (atom) of the package to install",
        )
        p.add_argument(
            "-f",
            "--fetch-only",
            action="store_true",
            help="Fetch distribution files only without installing",
        )
        p.add_argument(
            "--host",
            type=str,
            default=get_native_host(),
            help="Override the host architecture (normally not needed)",
        )
        p.add_argument(
            "--reinstall",
            action="store_true",
            help="Force re-installation of already installed packages",
        )

    @classmethod
    def main(cls, cfg: GlobalConfig, args: argparse.Namespace) -> int:
        host = args.host
        atom_strs: set[str] = set(args.atom)
        fetch_only = args.fetch_only
        reinstall = args.reinstall

        mr = cfg.repo

        return do_install_atoms(
            cfg,
            mr,
            atom_strs,
            canonicalized_host=canonicalize_host_str(host),
            fetch_only=fetch_only,
            reinstall=reinstall,
        )


class UninstallCommand(
    RootCommand,
    cmd="uninstall",
    aliases=["remove", "rm"],
    help="Uninstall installed packages",
):
    @classmethod
    def configure_args(cls, gc: GlobalConfig, p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "atom",
            type=str,
            nargs="+",
            help="Specifier (atom) of the package to uninstall",
        )
        p.add_argument(
            "--host",
            type=str,
            default=get_native_host(),
            help="Override the host architecture (normally not needed)",
        )
        p.add_argument(
            "-y",
            "--yes",
            action="store_true",
            dest="assume_yes",
            help="Assume yes to all prompts",
        )

    @classmethod
    def main(cls, cfg: GlobalConfig, args: argparse.Namespace) -> int:
        host: str = args.host
        atom_strs: set[str] = set(args.atom)
        assume_yes: bool = args.assume_yes

        return do_uninstall_atoms(
            cfg,
            cfg.repo,
            atom_strs,
            canonicalized_host=canonicalize_host_str(host),
            assume_yes=assume_yes,
        )
