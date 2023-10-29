import argparse
import platform
from urllib.parse import urljoin

from rich import print

from ruyi import is_debug

from ..config import RuyiConfig
from .repo import MetadataRepo
from .pkg_manifest import PackageManifest


def cli_list(args: argparse.Namespace) -> int:
    config = RuyiConfig.load_from_config()
    mr = MetadataRepo(
        config.get_repo_dir(), config.get_repo_url(), config.get_repo_branch()
    )

    for pm_data in mr.iter_pkg_manifests():
        pm = PackageManifest(pm_data)
        print(
            f"[bold]## [green]{pm.name}[/green] [yellow]({pm.slug})[/yellow][/bold]\n"
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


def cli_install(args: argparse.Namespace) -> int:
    host = platform.machine()
    slugs: set[str] = set(args.slug)
    if is_debug():
        print(f"[cyan]debug:[/cyan] about to install for host {host}: {slugs}")

    config = RuyiConfig.load_from_config()
    mr = MetadataRepo(
        config.get_repo_dir(), config.get_repo_url(), config.get_repo_branch()
    )

    repo_cfg = mr.get_config()

    # TODO: somehow don't traverse the entire repo?
    # Currently this isn't a problem due to the repo's small size, but it might
    # become necessary in the future.
    pms_to_install: list[PackageManifest] = []
    for pm_data in mr.iter_pkg_manifests():
        pm = PackageManifest(pm_data)
        if pm.slug not in slugs:
            continue

        pms_to_install.append(pm)

    # check non-existent slugs
    found_slugs = set(pm.slug for pm in pms_to_install)
    nonexistent_slugs = slugs.difference(found_slugs)
    if nonexistent_slugs:
        print(
            f"[bold][red]fatal error:[/red][/bold] {nonexistent_slugs} not found in the repository"
        )
        return 1

    for pm in pms_to_install:
        bm = pm.binary_metadata
        if bm is None:
            print(
                f"[bold][red]fatal error[/red][/bold]: don't know how to handle non-binary package {pm.slug}"
            )
            return 2

        dfs = pm.distfiles()

        distfiles_for_host = bm.get_distfile_names_for_host(host)
        if not distfiles_for_host:
            print(
                f"[bold][red]fatal error[/red][/bold]: package {pm.slug} declares no binary for host {host}"
            )
            return 2

        dist_url_base = repo_cfg["dist"]
        for df_name in distfiles_for_host:
            df_decl = dfs[df_name]
            url = urljoin(dist_url_base, f"distfiles/{df_name}")
            if is_debug():
                print(f"[cyan]debug:[/cyan] about to download {url}")

    return 0
