from itertools import chain

from ..config import GlobalConfig
from ..log import RuyiLogger
from ..utils.porcelain import PorcelainOutput
from .augmented_pkg import AugmentedPkg
from .list_filter import ListFilter
from .pkg_manifest import BoundPackageManifest


def do_list(
    cfg: GlobalConfig,
    filters: ListFilter,
    verbose: bool,
) -> int:
    logger = cfg.logger

    if not filters:
        if cfg.is_porcelain:
            # we don't want to print message for humans in case of porcelain
            # mode, but we don't want to retain the old behavior of listing
            # all packages either
            return 1

        logger.F("no filter specified for list operation")
        logger.I(
            "for the old behavior of listing all packages, try [yellow]ruyi list --name-contains ''[/]"
        )
        return 1

    augmented_pkgs = list(AugmentedPkg.yield_from_repo(cfg, cfg.repo, filters))

    if cfg.is_porcelain:
        return _do_list_porcelain(augmented_pkgs)

    if not verbose:
        return _do_list_non_verbose(logger, augmented_pkgs)

    for i, ver in enumerate(chain(*(ap.versions for ap in augmented_pkgs))):
        if i > 0:
            logger.stdout("\n")

        _print_pkg_detail(logger, ver.pm, cfg.lang_code)

    return 0


def _do_list_non_verbose(
    logger: RuyiLogger,
    augmented_pkgs: list[AugmentedPkg],
) -> int:
    logger.stdout("List of available packages:\n")

    for ap in augmented_pkgs:
        logger.stdout(f"* [bold green]{ap.category}/{ap.name}[/]")
        for ver in ap.versions:
            if ver.remarks:
                comments_str = (
                    f" ({', '.join(r.as_rich_markup() for r in ver.remarks)})"
                )
            else:
                comments_str = ""
            slug_str = f" slug: [yellow]{ver.pm.slug}[/]" if ver.pm.slug else ""
            logger.stdout(f"  - [blue]{ver.pm.semver}[/]{comments_str}{slug_str}")

    return 0


def _do_list_porcelain(augmented_pkgs: list[AugmentedPkg]) -> int:
    with PorcelainOutput() as po:
        for ap in augmented_pkgs:
            po.emit(ap.to_porcelain())

    return 0


def _print_pkg_detail(
    logger: RuyiLogger,
    pm: BoundPackageManifest,
    lang_code: str,
) -> None:
    logger.stdout(f"[bold]## [green]{pm.category}/{pm.name}[/] [blue]{pm.ver}[/][/]\n")

    if pm.slug is not None:
        logger.stdout(f"* Slug: [yellow]{pm.slug}[/]")
    else:
        logger.stdout("* Slug: (none)")
    logger.stdout(f"* Package kind: {sorted(pm.kind)}")
    logger.stdout(f"* Vendor: {pm.vendor_name}")
    if upstream_ver := pm.upstream_version:
        logger.stdout(f"* Upstream version number: {upstream_ver}")
    else:
        logger.stdout("* Upstream version number: (undeclared)")
    logger.stdout("")

    sv = pm.service_level
    if sv.has_known_issues:
        logger.stdout("\nPackage has known issue(s):\n")
        for x in sv.render_known_issues(pm.repo.messages, lang_code):
            logger.stdout(x, end="\n\n")

    df = pm.distfiles
    logger.stdout(f"Package declares {len(df)} distfile(s):\n")
    for dd in df.values():
        logger.stdout(f"* [green]{dd.name}[/]")
        logger.stdout(f"    - Size: [yellow]{dd.size}[/] bytes")
        for kind, csum in dd.checksums.items():
            logger.stdout(f"    - {kind.upper()}: [yellow]{csum}[/]")

    if bm := pm.binary_metadata:
        logger.stdout("\n### Binary artifacts\n")
        for host, data in bm.data.items():
            logger.stdout(f"* Host [green]{host}[/]:")
            logger.stdout(f"    - Distfiles: {data['distfiles']}")
            if cmds := data.get("commands"):
                logger.stdout("    - Available command(s):")
                for k in sorted(cmds.keys()):
                    logger.stdout(f"        - [green]{k}[/]")

    if tm := pm.toolchain_metadata:
        logger.stdout("\n### Toolchain metadata\n")
        logger.stdout(f"* Target: [bold green]{tm.target}[/]")
        logger.stdout(f"* Quirks: {tm.quirks}")
        logger.stdout("* Components:")
        for tc in tm.components:
            logger.stdout(f'    - {tc["name"]} [bold green]{tc["version"]}[/]')
