import argparse
import os.path
import pathlib
import shutil
from urllib.parse import urljoin

from rich import print

from .. import log

from ..config import RuyiConfig
from .distfile import Distfile
from .repo import MetadataRepo
from .pkg_manifest import PackageManifest


def cli_list(args: argparse.Namespace) -> int:
    config = RuyiConfig.load_from_config()
    mr = MetadataRepo(
        config.get_repo_dir(), config.get_repo_url(), config.get_repo_branch()
    )

    for pm in mr.iter_pkg_manifests():
        print(
            f"[bold]## [green]{pm.desc}[/green] [yellow]({pm.slug})[/yellow][/bold]\n"
        )
        print(f"* Package kind: {sorted(pm.kind)}")
        print(f"* Vendor: {pm.vendor_name}\n")

        df = pm.distfiles()
        print(f"Package declares {len(df)} distfiles:\n")
        for dd in df.values():
            print(f"* [green]{dd.name}[/green]")
            print(f"    - Size: [yellow]{dd.size}[/yellow] bytes")
            for kind, csum in dd.checksums.items():
                print(f"    - {kind.upper()}: [yellow]{csum}[/yellow]")

        bm = pm.binary_metadata
        if bm is not None:
            print("\n### Binary artifacts\n")
            for host, distfile_names in bm.data.items():
                print(f"* Host [green]{host}[/green]: {distfile_names}")

        tm = pm.toolchain_metadata
        if tm is not None:
            print("\n### Toolchain metadata\n")
            print(f"* Target: [bold][green]{tm.target}[/green][/bold]")
            print(f"* Flavors: {tm.flavors}")
            print("* Components:")
            for tc in tm.components:
                print(f'    - {tc["name"]} [bold][green]{tc["version"]}[/green][/bold]')

    return 0


def make_distfile_url(base: str, name: str) -> str:
    # urljoin can't be used because it trims the basename part if base is not
    # `/`-suffixed
    return f"{base}distfiles/{name}" if base[-1] == "/" else f"{base}/dist/{name}"


def is_root_likely_populated(root: str) -> bool:
    try:
        return any(os.scandir(root))
    except FileNotFoundError:
        return False


def cli_install(args: argparse.Namespace) -> int:
    host = args.host
    slugs: set[str] = set(args.slug)
    fetch_only = args.fetch_only
    reinstall = args.reinstall
    log.D(f"about to install for host {host}: {slugs}")

    config = RuyiConfig.load_from_config()
    mr = MetadataRepo(
        config.get_repo_dir(), config.get_repo_url(), config.get_repo_branch()
    )

    repo_cfg = mr.get_config()

    # TODO: somehow don't traverse the entire repo?
    # Currently this isn't a problem due to the repo's small size, but it might
    # become necessary in the future.
    pms_to_install: list[PackageManifest] = []
    for pm in mr.iter_pkg_manifests():
        if pm.slug not in slugs:
            continue

        pms_to_install.append(pm)

    # check non-existent slugs
    found_slugs = set(pm.slug for pm in pms_to_install)
    nonexistent_slugs = slugs.difference(found_slugs)
    if nonexistent_slugs:
        log.F(f"{nonexistent_slugs} not found in the repository")
        return 1

    for pm in pms_to_install:
        bm = pm.binary_metadata
        if bm is None:
            log.F(
                f"don't know how to handle non-binary package [green]{pm.slug}[/green]"
            )
            return 2

        install_root = config.get_toolchain_install_root(host, pm.slug)
        if is_root_likely_populated(install_root):
            if reinstall:
                log.W(
                    f"package [green]{pm.slug}[/green] seems already installed; purging and re-installing due to [yellow]--reinstall[/yellow]"
                )
                shutil.rmtree(install_root)
                pathlib.Path(install_root).mkdir(parents=True)
            else:
                log.I(f"skipping already installed package [green]{pm.slug}[/green]")
                continue
        else:
            pathlib.Path(install_root).mkdir(parents=True, exist_ok=True)

        dfs = pm.distfiles()

        distfiles_for_host = bm.get_distfile_names_for_host(host)
        if not distfiles_for_host:
            log.F(
                f"package [green]{pm.slug}[/green] declares no binary for host {host}"
            )
            return 2

        dist_url_base = repo_cfg["dist"]
        for df_name in distfiles_for_host:
            df_decl = dfs[df_name]
            url = make_distfile_url(dist_url_base, df_name)
            dest = os.path.join(config.ensure_distfiles_dir(), df_name)
            log.I(f"downloading {url} to {dest}")
            df = Distfile(url, dest, df_decl.size, df_decl.checksums)
            df.ensure()

            if fetch_only:
                log.D(
                    "skipping installation because [yellow]--fetch-only[/yellow] is given"
                )
                continue

            log.I(
                f"extracting [green]{df_name}[/green] for package [green]{pm.slug}[/green]"
            )
            df.unpack(install_root)

        log.I(
            f"package [green]{pm.slug}[/green] installed to [yellow]{install_root}[/yellow]"
        )

    return 0
