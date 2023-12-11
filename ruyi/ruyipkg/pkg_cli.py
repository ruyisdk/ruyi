import argparse
import os.path
import pathlib
import shutil

from .. import log

print = log.stdout

from ..config import GlobalConfig
from .atom import Atom
from .distfile import Distfile
from .repo import MetadataRepo
from .pkg_manifest import PackageManifest
from .unpack import ensure_unpack_cmd_for_distfile


def cli_list(args: argparse.Namespace) -> int:
    verbose = args.verbose

    config = GlobalConfig.load_from_config()
    mr = MetadataRepo(
        config.get_repo_dir(), config.get_repo_url(), config.get_repo_branch()
    )

    if not verbose:
        return do_list_non_verbose(mr)

    first = True
    for _, _, pkg_vers in mr.iter_pkgs():
        for pm in pkg_vers.values():
            if first:
                first = False
            else:
                print("\n")

            print_pkg_detail(pm)

    return 0


def do_list_non_verbose(mr: MetadataRepo) -> int:
    print("List of available packages:\n")

    for category, pkg_name, pkg_vers in mr.iter_pkgs():
        print(f"* [bold green]{category}/{pkg_name}[/bold green]")
        semvers = [pm.semver for pm in pkg_vers.values()]
        semvers.sort(reverse=True)
        found_latest = False
        for i, sv in enumerate(semvers):
            pm = pkg_vers[str(sv)]

            latest = False
            latest_prerelease = i == 0
            prerelease = pm.is_prerelease
            if not found_latest and not prerelease:
                latest = True
                found_latest = True

            comments: list[str] = []
            if latest or latest_prerelease or prerelease:
                if prerelease:
                    comments.append("prerelease")
                if latest:
                    comments.append("latest")
                if latest_prerelease and not latest:
                    comments.append("latest-prerelease")
            if bm := pm.binary_metadata:
                if not bm.is_available_for_current_host:
                    comments.append("[red]no binary for current host[/red]")

            comments_str = f" ({', '.join(comments)})"

            slug_str = f" slug: [yellow]{pm.slug}[/yellow]" if pm.slug else ""

            print(f"  - [blue]{sv}[/blue]{comments_str}{slug_str}")

    return 0


def print_pkg_detail(pm: PackageManifest) -> None:
    print(
        f"[bold]## [green]{pm.category}/{pm.name}[/green] [blue]{pm.ver}[/blue][/bold]\n"
    )

    if pm.slug is not None:
        print(f"* Slug: [yellow]{pm.slug}[/yellow]")
    else:
        print(f"* Slug: (none)")
    print(f"* Package kind: {sorted(pm.kind)}")
    print(f"* Vendor: {pm.vendor_name}\n")

    df = pm.distfiles()
    print(f"Package declares {len(df)} distfile(s):\n")
    for dd in df.values():
        print(f"* [green]{dd.name}[/green]")
        print(f"    - Size: [yellow]{dd.size}[/yellow] bytes")
        for kind, csum in dd.checksums.items():
            print(f"    - {kind.upper()}: [yellow]{csum}[/yellow]")

    if bm := pm.binary_metadata:
        print("\n### Binary artifacts\n")
        for host, distfile_names in bm.data.items():
            print(f"* Host [green]{host}[/green]: {distfile_names}")

    if tm := pm.toolchain_metadata:
        print("\n### Toolchain metadata\n")
        print(f"* Target: [bold][green]{tm.target}[/green][/bold]")
        print(f"* Flavors: {tm.flavors}")
        print("* Components:")
        for tc in tm.components:
            print(f'    - {tc["name"]} [bold][green]{tc["version"]}[/green][/bold]')


def make_distfile_url(base: str, name: str) -> str:
    # urljoin can't be used because it trims the basename part if base is not
    # `/`-suffixed
    return f"{base}dist/{name}" if base[-1] == "/" else f"{base}/dist/{name}"


def is_root_likely_populated(root: str) -> bool:
    try:
        return any(os.scandir(root))
    except FileNotFoundError:
        return False


def cli_extract(args: argparse.Namespace) -> int:
    host = args.host
    atom_strs: set[str] = set(args.atom)
    log.D(f"about to extract for host {host}: {atom_strs}")

    config = GlobalConfig.load_from_config()
    mr = MetadataRepo(
        config.get_repo_dir(), config.get_repo_url(), config.get_repo_branch()
    )

    repo_cfg = mr.get_config()

    for a_str in atom_strs:
        a = Atom.parse(a_str)
        pm = a.match_in_repo(mr, config.include_prereleases)
        if pm is None:
            log.F(f"atom {a_str} matches no package in the repository")
            return 1
        pkg_name = pm.name_for_installation

        bm = pm.binary_metadata
        sm = pm.source_metadata
        if bm is None and sm is None:
            log.F(f"don't know how to extract package [green]{pkg_name}[/green]")
            return 2

        if bm is not None and sm is not None:
            log.F(
                f"cannot handle package [green]{pkg_name}[/green]: package is both binary and source"
            )
            return 2

        distfiles_for_host: list[str] | None = None
        if bm is not None:
            distfiles_for_host = bm.get_distfile_names_for_host(host)
        elif sm is not None:
            distfiles_for_host = sm.get_distfile_names_for_host(host)

        if not distfiles_for_host:
            log.F(
                f"package [green]{pkg_name}[/green] declares no distfile for host {host}"
            )
            return 2

        dfs = pm.distfiles()

        dist_url_base = repo_cfg["dist"]
        for df_name in distfiles_for_host:
            df_decl = dfs[df_name]
            url = make_distfile_url(dist_url_base, df_name)
            dest = os.path.join(config.ensure_distfiles_dir(), df_name)
            ensure_unpack_cmd_for_distfile(dest)
            log.I(f"downloading {url} to {dest}")
            df = Distfile(url, dest, df_decl)
            df.ensure()

            log.I(
                f"extracting [green]{df_name}[/green] for package [green]{pkg_name}[/green]"
            )
            # unpack into CWD
            df.unpack(None)

        log.I(
            f"package [green]{pkg_name}[/green] extracted to current working directory"
        )

    return 0


def cli_install(args: argparse.Namespace) -> int:
    host = args.host
    atom_strs: set[str] = set(args.atom)
    fetch_only = args.fetch_only
    reinstall = args.reinstall
    log.D(f"about to install for host {host}: {atom_strs}")

    config = GlobalConfig.load_from_config()
    mr = MetadataRepo(
        config.get_repo_dir(), config.get_repo_url(), config.get_repo_branch()
    )

    repo_cfg = mr.get_config()

    for a_str in atom_strs:
        a = Atom.parse(a_str)
        pm = a.match_in_repo(mr, config.include_prereleases)
        if pm is None:
            log.F(f"atom {a_str} matches no package in the repository")
            return 1
        pkg_name = pm.name_for_installation

        bm = pm.binary_metadata
        if bm is None:
            log.F(
                f"don't know how to handle non-binary package [green]{pkg_name}[/green]"
            )
            return 2

        install_root = config.global_binary_install_root(host, pkg_name)
        if is_root_likely_populated(install_root):
            if reinstall:
                log.W(
                    f"package [green]{pkg_name}[/green] seems already installed; purging and re-installing due to [yellow]--reinstall[/yellow]"
                )
                shutil.rmtree(install_root)
                pathlib.Path(install_root).mkdir(parents=True)
            else:
                log.I(f"skipping already installed package [green]{pkg_name}[/green]")
                continue
        else:
            pathlib.Path(install_root).mkdir(parents=True, exist_ok=True)

        dfs = pm.distfiles()

        distfiles_for_host = bm.get_distfile_names_for_host(host)
        if not distfiles_for_host:
            log.F(
                f"package [green]{pkg_name}[/green] declares no binary for host {host}"
            )
            return 2

        dist_url_base = repo_cfg["dist"]
        for df_name in distfiles_for_host:
            df_decl = dfs[df_name]
            url = make_distfile_url(dist_url_base, df_name)
            dest = os.path.join(config.ensure_distfiles_dir(), df_name)
            ensure_unpack_cmd_for_distfile(dest)
            log.I(f"downloading {url} to {dest}")
            df = Distfile(url, dest, df_decl)
            df.ensure()

            if fetch_only:
                log.D(
                    "skipping installation because [yellow]--fetch-only[/yellow] is given"
                )
                continue

            log.I(
                f"extracting [green]{df_name}[/green] for package [green]{pkg_name}[/green]"
            )
            df.unpack(install_root)

        log.I(
            f"package [green]{pkg_name}[/green] installed to [yellow]{install_root}[/yellow]"
        )

    return 0
