from itertools import chain

from ..config import GlobalConfig
from ..i18n import _
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

        logger.F(_("no filter specified for list operation"))
        logger.I(
            _(
                "for the old behavior of listing all packages, try [yellow]ruyi list --all[/]"
            )
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
    logger.stdout(_("List of available packages:\n"))

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
        logger.stdout(_("* Slug: [yellow]{slug}[/]").format(slug=pm.slug))
    else:
        logger.stdout(_("* Slug: (none)"))
    logger.stdout(_("* Package kind: {kind}").format(kind=sorted(pm.kind)))
    logger.stdout(_("* Vendor: {vendor}").format(vendor=pm.vendor_name))
    if upstream_ver := pm.upstream_version:
        logger.stdout(
            _("* Upstream version number: {version}").format(version=upstream_ver)
        )
    else:
        logger.stdout(_("* Upstream version number: (undeclared)"))
    logger.stdout("")

    sv = pm.service_level
    if sv.has_known_issues:
        logger.stdout(_("\nPackage has known issue(s):\n"))
        for x in sv.render_known_issues(pm.repo.messages, lang_code):
            logger.stdout(x, end="\n\n")

    df = pm.distfiles
    logger.stdout(_("Package declares {count} distfile(s):\n").format(count=len(df)))
    for dd in df.values():
        logger.stdout(f"* [green]{dd.name}[/]")
        logger.stdout(_("    - Size: [yellow]{size}[/] bytes").format(size=dd.size))
        for kind, csum in dd.checksums.items():
            logger.stdout(f"    - {kind.upper()}: [yellow]{csum}[/]")

    if bm := pm.binary_metadata:
        logger.stdout(_("\n### Binary artifacts\n"))
        for host, data in bm.data.items():
            logger.stdout(_("* Host [green]{host}[/]:").format(host=host))
            logger.stdout(
                _("    - Distfiles: {distfiles}").format(distfiles=data["distfiles"])
            )
            if cmds := data.get("commands"):
                logger.stdout(_("    - Available command(s):"))
                for k in sorted(cmds.keys()):
                    logger.stdout(f"        - [green]{k}[/]")

    if tm := pm.toolchain_metadata:
        logger.stdout(_("\n### Toolchain metadata\n"))
        logger.stdout(_("* Target: [bold green]{target}[/]").format(target=tm.target))
        logger.stdout(_("* Quirks: {quirks}").format(quirks=tm.quirks))
        logger.stdout(_("* Components:"))
        for tc in tm.components:
            logger.stdout(f'    - {tc["name"]} [bold green]{tc["version"]}[/]')
