import argparse

from rich import print

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
