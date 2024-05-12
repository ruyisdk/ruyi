import argparse
from enum import StrEnum
import os.path
import pathlib
import shutil
import tempfile
from typing import Iterable, Self

from ..utils.porcelain import PorcelainEntity, PorcelainEntityType, PorcelainOutput
from .host import canonicalize_host_str
from .. import is_porcelain, log
from ..config import GlobalConfig
from .atom import Atom
from .distfile import Distfile
from .repo import MetadataRepo
from .pkg_manifest import PackageManifest, PackageManifestType
from .unpack import ensure_unpack_cmd_for_method


def cli_list(args: argparse.Namespace) -> int:
    verbose = args.verbose

    config = GlobalConfig.load_from_config()
    mr = MetadataRepo(config)

    augmented_pkgs = list(AugmentedPkgManifest.yield_from_repo(mr))

    if is_porcelain():
        return do_list_porcelain(augmented_pkgs)

    if not verbose:
        return do_list_non_verbose(augmented_pkgs)

    for i, ap in enumerate(augmented_pkgs):
        if i > 0:
            log.stdout("\n")

        print_pkg_detail(ap.pm)

    return 0


class PkgRemark(StrEnum):
    Latest = "latest"
    LatestPreRelease = "latest-prerelease"
    NoBinaryForCurrentHost = "no-binary-for-current-host"
    PreRelease = "prerelease"

    def as_rich_markup(self) -> str:
        match self:
            case self.Latest:
                return "latest"
            case self.LatestPreRelease:
                return "latest-prerelease"
            case self.NoBinaryForCurrentHost:
                return "[red]no binary for current host[/red]"
            case self.PreRelease:
                return "prerelease"
        return ""


class AugmentedPkgManifest:
    def __init__(self, pm: PackageManifest, remarks: list[PkgRemark]) -> None:
        self.pm = pm
        self.remarks = remarks

    def to_porcelain(self) -> "PorcelainPkgListOutputV1":
        return {
            "ty": PorcelainEntityType.PkgListOutputV1,
            "category": self.pm.category,
            "name": self.pm.name,
            "semver": str(self.pm.semver),
            "pm": self.pm.to_raw(),
            "remarks": self.remarks,
        }

    @classmethod
    def yield_from_repo(cls, mr: MetadataRepo) -> Iterable[Self]:
        for _, _, pkg_vers in mr.iter_pkgs():
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

                remarks: list[PkgRemark] = []
                if latest or latest_prerelease or prerelease:
                    if prerelease:
                        remarks.append(PkgRemark.PreRelease)
                    if latest:
                        remarks.append(PkgRemark.Latest)
                    if latest_prerelease and not latest:
                        remarks.append(PkgRemark.LatestPreRelease)
                if bm := pm.binary_metadata:
                    if not bm.is_available_for_current_host:
                        remarks.append(PkgRemark.NoBinaryForCurrentHost)

                yield cls(pm, remarks)


def do_list_non_verbose(augmented_pkgs: list[AugmentedPkgManifest]) -> int:
    log.stdout("List of available packages:\n")

    for ap in augmented_pkgs:
        log.stdout(f"* [bold green]{ap.pm.category}/{ap.pm.name}[/bold green]")
        comments_str = f" ({', '.join(r.as_rich_markup() for r in ap.remarks)})"
        slug_str = f" slug: [yellow]{ap.pm.slug}[/yellow]" if ap.pm.slug else ""
        log.stdout(f"  - [blue]{ap.pm.semver}[/blue]{comments_str}{slug_str}")

    return 0


class PorcelainPkgListOutputV1(PorcelainEntity):
    category: str
    name: str
    semver: str
    pm: PackageManifestType
    remarks: list[PkgRemark]


def do_list_porcelain(augmented_pkgs: list[AugmentedPkgManifest]) -> int:
    with PorcelainOutput() as po:
        for ap in augmented_pkgs:
            po.emit(ap.to_porcelain())

    return 0


def print_pkg_detail(pm: PackageManifest) -> None:
    log.stdout(
        f"[bold]## [green]{pm.category}/{pm.name}[/green] [blue]{pm.ver}[/blue][/bold]\n"
    )

    if pm.slug is not None:
        log.stdout(f"* Slug: [yellow]{pm.slug}[/yellow]")
    else:
        log.stdout("* Slug: (none)")
    log.stdout(f"* Package kind: {sorted(pm.kind)}")
    log.stdout(f"* Vendor: {pm.vendor_name}\n")

    df = pm.distfiles()
    log.stdout(f"Package declares {len(df)} distfile(s):\n")
    for dd in df.values():
        log.stdout(f"* [green]{dd.name}[/green]")
        log.stdout(f"    - Size: [yellow]{dd.size}[/yellow] bytes")
        for kind, csum in dd.checksums.items():
            log.stdout(f"    - {kind.upper()}: [yellow]{csum}[/yellow]")

    if bm := pm.binary_metadata:
        log.stdout("\n### Binary artifacts\n")
        for host, distfile_names in bm.data.items():
            log.stdout(f"* Host [green]{host}[/green]: {distfile_names}")

    if tm := pm.toolchain_metadata:
        log.stdout("\n### Toolchain metadata\n")
        log.stdout(f"* Target: [bold][green]{tm.target}[/green][/bold]")
        log.stdout(f"* Flavors: {tm.flavors}")
        log.stdout("* Components:")
        for tc in tm.components:
            log.stdout(
                f'    - {tc["name"]} [bold][green]{tc["version"]}[/green][/bold]'
            )


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
    mr = MetadataRepo(config)

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

        for df_name in distfiles_for_host:
            df_decl = dfs[df_name]
            urls = mr.get_distfile_urls(df_decl)
            dest = os.path.join(config.ensure_distfiles_dir(), df_name)
            ensure_unpack_cmd_for_method(df_decl.unpack_method)
            df = Distfile(urls, dest, df_decl)
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

    config = GlobalConfig.load_from_config()
    mr = MetadataRepo(config)

    return do_install_atoms(
        config,
        mr,
        atom_strs,
        canonicalized_host=canonicalize_host_str(host),
        fetch_only=fetch_only,
        reinstall=reinstall,
    )


def do_install_atoms(
    config: GlobalConfig,
    mr: MetadataRepo,
    atom_strs: set[str],
    *,
    canonicalized_host: str,
    fetch_only: bool,
    reinstall: bool,
) -> int:
    log.D(f"about to install for host {canonicalized_host}: {atom_strs}")

    for a_str in atom_strs:
        a = Atom.parse(a_str)
        pm = a.match_in_repo(mr, config.include_prereleases)
        if pm is None:
            log.F(f"atom {a_str} matches no package in the repository")
            return 1
        pkg_name = pm.name_for_installation

        if pm.binary_metadata is not None:
            ret = do_install_binary_pkg(
                config,
                mr,
                pm,
                canonicalized_host,
                fetch_only,
                reinstall,
            )
            if ret != 0:
                return ret
            continue

        if pm.blob_metadata is not None:
            ret = do_install_blob_pkg(config, mr, pm, fetch_only, reinstall)
            if ret != 0:
                return ret
            continue

        log.F(f"don't know how to handle non-binary package [green]{pkg_name}[/green]")
        return 2

    return 0


def do_install_binary_pkg(
    config: GlobalConfig,
    mr: MetadataRepo,
    pm: PackageManifest,
    canonicalized_host: str,
    fetch_only: bool,
    reinstall: bool,
) -> int:
    bm = pm.binary_metadata
    assert bm is not None

    pkg_name = pm.name_for_installation
    install_root = config.global_binary_install_root(canonicalized_host, pkg_name)
    if is_root_likely_populated(install_root):
        if not reinstall:
            log.I(f"skipping already installed package [green]{pkg_name}[/green]")
            return 0

        log.W(
            f"package [green]{pkg_name}[/green] seems already installed; purging and re-installing due to [yellow]--reinstall[/yellow]"
        )
        shutil.rmtree(install_root)

    ir_parent = pathlib.Path(install_root).resolve().parent
    ir_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".ruyi-tmp", dir=ir_parent) as tmp_root:
        ret = do_install_binary_pkg_to(
            config,
            mr,
            pm,
            canonicalized_host,
            fetch_only,
            tmp_root,
        )
        if ret != 0:
            return ret
        os.rename(tmp_root, install_root)

    log.I(
        f"package [green]{pkg_name}[/green] installed to [yellow]{install_root}[/yellow]"
    )
    return 0


def do_install_binary_pkg_to(
    config: GlobalConfig,
    mr: MetadataRepo,
    pm: PackageManifest,
    canonicalized_host: str,
    fetch_only: bool,
    install_root: str,
) -> int:
    bm = pm.binary_metadata
    assert bm is not None

    dfs = pm.distfiles()

    pkg_name = pm.name_for_installation
    distfiles_for_host = bm.get_distfile_names_for_host(canonicalized_host)
    if not distfiles_for_host:
        log.F(
            f"package [green]{pkg_name}[/green] declares no binary for host {canonicalized_host}"
        )
        return 2

    for df_name in distfiles_for_host:
        df_decl = dfs[df_name]
        urls = mr.get_distfile_urls(df_decl)
        dest = os.path.join(config.ensure_distfiles_dir(), df_name)
        ensure_unpack_cmd_for_method(df_decl.unpack_method)
        df = Distfile(urls, dest, df_decl)
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

    return 0


def do_install_blob_pkg(
    config: GlobalConfig,
    mr: MetadataRepo,
    pm: PackageManifest,
    fetch_only: bool,
    reinstall: bool,
) -> int:
    bm = pm.blob_metadata
    assert bm is not None

    pkg_name = pm.name_for_installation
    install_root = config.global_blob_install_root(pkg_name)
    if is_root_likely_populated(install_root):
        if not reinstall:
            log.I(f"skipping already installed package [green]{pkg_name}[/green]")
            return 0

        log.W(
            f"package [green]{pkg_name}[/green] seems already installed; purging and re-installing due to [yellow]--reinstall[/yellow]"
        )
        shutil.rmtree(install_root)

    ir_parent = pathlib.Path(install_root).resolve().parent
    ir_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".ruyi-tmp", dir=ir_parent) as tmp_root:
        ret = do_install_blob_pkg_to(
            config,
            mr,
            pm,
            fetch_only,
            tmp_root,
        )
        if ret != 0:
            return ret
        os.rename(tmp_root, install_root)

    log.I(
        f"package [green]{pkg_name}[/green] installed to [yellow]{install_root}[/yellow]"
    )
    return 0


def do_install_blob_pkg_to(
    config: GlobalConfig,
    mr: MetadataRepo,
    pm: PackageManifest,
    fetch_only: bool,
    install_root: str,
) -> int:
    bm = pm.blob_metadata
    assert bm is not None

    pkg_name = pm.name_for_installation
    dfs = pm.distfiles()
    distfile_names = bm.get_distfile_names()
    if not distfile_names:
        log.F(f"package [green]{pkg_name}[/green] declares no blob distfile")
        return 2

    for df_name in distfile_names:
        df_decl = dfs[df_name]
        urls = mr.get_distfile_urls(df_decl)
        dest = os.path.join(config.ensure_distfiles_dir(), df_name)
        ensure_unpack_cmd_for_method(df_decl.unpack_method)
        df = Distfile(urls, dest, df_decl)
        df.ensure()

        if fetch_only:
            log.D(
                "skipping installation because [yellow]--fetch-only[/yellow] is given"
            )
            continue

        log.I(
            f"extracting [green]{df_name}[/green] for package [green]{pkg_name}[/green]"
        )
        df.unpack_or_symlink(install_root)

    return 0
