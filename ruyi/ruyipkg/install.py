import os
import pathlib
import shutil
import tempfile
from typing import Any

from ruyi.ruyipkg.state import BoundInstallationStateStore

from ..cli.user_input import ask_for_yesno_confirmation
from ..config import GlobalConfig
from ..telemetry.scope import TelemetryScope
from .atom import Atom
from .distfile import Distfile
from .host import RuyiHost
from .pkg_manifest import BoundPackageManifest
from .repo import MetadataRepo
from .unpack import ensure_unpack_cmd_for_method


def is_root_likely_populated(root: str) -> bool:
    try:
        return any(os.scandir(root))
    except FileNotFoundError:
        return False


def do_extract_atoms(
    cfg: GlobalConfig,
    mr: MetadataRepo,
    atom_strs: set[str],
    *,
    canonicalized_host: str | RuyiHost,
    dest_dir: os.PathLike[Any] | None,  # None for CWD
    extract_without_subdir: bool,
    fetch_only: bool,
) -> int:
    logger = cfg.logger
    logger.D(f"about to extract for host {canonicalized_host}: {atom_strs}")

    mr = cfg.repo

    for a_str in atom_strs:
        a = Atom.parse(a_str)
        pm = a.match_in_repo(mr, cfg.include_prereleases)
        if pm is None:
            logger.F(f"atom {a_str} matches no package in the repository")
            return 1

        sv = pm.service_level
        if sv.has_known_issues:
            logger.W("package has known issue(s)")
            for s in sv.render_known_issues(pm.repo.messages, cfg.lang_code):
                logger.I(s)

        ret = _do_extract_pkg(
            cfg,
            pm,
            canonicalized_host=canonicalized_host,
            fetch_only=fetch_only,
            dest_dir=dest_dir,
            extract_without_subdir=extract_without_subdir,
        )
        if ret != 0:
            return ret

    return 0


def _do_extract_pkg(
    cfg: GlobalConfig,
    pm: BoundPackageManifest,
    *,
    canonicalized_host: str | RuyiHost,
    dest_dir: os.PathLike[Any] | None,  # None for CWD
    extract_without_subdir: bool,
    fetch_only: bool,
) -> int:
    logger = cfg.logger

    pkg_name = pm.name_for_installation

    if not extract_without_subdir:
        # extract into a subdirectory named <pkg_name>-<version>
        subdir_name = pm.name_for_installation
        if dest_dir is None:
            dest_dir = pathlib.Path(subdir_name)
        else:
            dest_dir = pathlib.Path(dest_dir) / subdir_name

    logger.D(f"about to extract {pm} to {dest_dir}")

    # Make sure destination directory exists
    if dest_dir is not None:
        dest_dir = pathlib.Path(dest_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)

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
        distfiles_for_host = bm.get_distfile_names_for_host(canonicalized_host)
    elif sm is not None:
        distfiles_for_host = sm.get_distfile_names_for_host(canonicalized_host)

    if not distfiles_for_host:
        logger.F(
            f"package [green]{pkg_name}[/] declares no distfile for host {canonicalized_host}"
        )
        return 2

    dfs = pm.distfiles

    for df_name in distfiles_for_host:
        df_decl = dfs[df_name]
        ensure_unpack_cmd_for_method(logger, df_decl.unpack_method)
        df = Distfile(df_decl, pm.repo)
        df.ensure(logger)

        if fetch_only:
            logger.D("skipping extraction because [yellow]--fetch-only[/] is given")
            continue

        logger.I(f"extracting [green]{df_name}[/] for package [green]{pkg_name}[/]")
        # unpack into destination
        df.unpack(dest_dir, logger)

    if not fetch_only:
        logger.I(
            f"package [green]{pkg_name}[/] has been extracted to {dest_dir}",
        )

    return 0


def do_install_atoms(
    config: GlobalConfig,
    mr: MetadataRepo,
    atom_strs: set[str],
    *,
    canonicalized_host: str | RuyiHost,
    fetch_only: bool,
    reinstall: bool,
) -> int:
    logger = config.logger
    logger.D(f"about to install for host {canonicalized_host}: {atom_strs}")

    for a_str in atom_strs:
        a = Atom.parse(a_str)
        pm = a.match_in_repo(mr, config.include_prereleases)
        if pm is None:
            logger.F(f"atom {a_str} matches no package in the repository")
            return 1
        pkg_name = pm.name_for_installation

        sv = pm.service_level
        if sv.has_known_issues:
            logger.W("package has known issue(s)")
            for s in sv.render_known_issues(pm.repo.messages, config.lang_code):
                logger.I(s)

        if tm := config.telemetry:
            tm.record(
                TelemetryScope(mr.repo_id),
                "repo:package-install-v1",
                atom=a_str,
                host=canonicalized_host,
                pkg_category=pm.category,
                pkg_kinds=pm.kind,
                pkg_name=pm.name,
                pkg_version=pm.ver,
            )

        if pm.binary_metadata is not None:
            ret = _do_install_binary_pkg(
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
            ret = _do_install_blob_pkg(config, mr, pm, fetch_only, reinstall)
            if ret != 0:
                return ret
            continue

        # the user may be trying to fetch a source-only package with `ruyi install --fetch-only`,
        # so try that too for better UX
        if fetch_only and pm.source_metadata is not None:
            ret = _do_extract_pkg(
                config,
                pm,
                canonicalized_host=canonicalized_host,
                dest_dir=None,  # unused in this case
                extract_without_subdir=False,  # unused in this case
                fetch_only=fetch_only,
            )
            if ret != 0:
                return ret
            continue

        logger.F(f"don't know how to handle non-binary package [green]{pkg_name}[/]")
        return 2

    return 0


def _do_install_binary_pkg(
    config: GlobalConfig,
    mr: MetadataRepo,
    pm: BoundPackageManifest,
    canonicalized_host: str | RuyiHost,
    fetch_only: bool,
    reinstall: bool,
) -> int:
    logger = config.logger
    bm = pm.binary_metadata
    assert bm is not None

    pkg_name = pm.name_for_installation
    install_root = config.global_binary_install_root(str(canonicalized_host), pkg_name)

    rgs = config.ruyipkg_global_state
    is_installed = rgs.is_package_installed(
        pm.repo_id,
        pm.category,
        pm.name,
        pm.ver,
        str(canonicalized_host),
    )

    # Fallback to directory check if not tracked in state
    if not is_installed and is_root_likely_populated(install_root):
        is_installed = True

    if is_installed:
        if not reinstall:
            logger.I(f"skipping already installed package [green]{pkg_name}[/]")
            return 0

        logger.W(
            f"package [green]{pkg_name}[/] seems already installed; purging and re-installing due to [yellow]--reinstall[/]"
        )
        # Remove from state tracking before purging
        rgs.remove_installation(
            pm.repo_id,
            pm.category,
            pm.name,
            pm.ver,
            str(canonicalized_host),
        )
        shutil.rmtree(install_root)

    ir_parent = pathlib.Path(install_root).resolve().parent
    ir_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".ruyi-tmp", dir=ir_parent) as tmp_root:
        ret = _do_install_binary_pkg_to(
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

    if not fetch_only:
        rgs.record_installation(
            repo_id=pm.repo_id,
            category=pm.category,
            name=pm.name,
            version=pm.ver,
            host=str(canonicalized_host),
            install_path=install_root,
        )

    logger.I(f"package [green]{pkg_name}[/] installed to [yellow]{install_root}[/]")
    return 0


def _do_install_binary_pkg_to(
    config: GlobalConfig,
    mr: MetadataRepo,
    pm: BoundPackageManifest,
    canonicalized_host: str | RuyiHost,
    fetch_only: bool,
    install_root: str,
) -> int:
    logger = config.logger
    bm = pm.binary_metadata
    assert bm is not None

    dfs = pm.distfiles

    pkg_name = pm.name_for_installation
    distfiles_for_host = bm.get_distfile_names_for_host(str(canonicalized_host))
    if not distfiles_for_host:
        logger.F(
            f"package [green]{pkg_name}[/] declares no binary for host {canonicalized_host}"
        )
        return 2

    for df_name in distfiles_for_host:
        df_decl = dfs[df_name]
        ensure_unpack_cmd_for_method(logger, df_decl.unpack_method)
        df = Distfile(df_decl, mr)
        df.ensure(logger)

        if fetch_only:
            logger.D("skipping installation because [yellow]--fetch-only[/] is given")
            continue

        logger.I(f"extracting [green]{df_name}[/] for package [green]{pkg_name}[/]")
        df.unpack(install_root, logger)

    return 0


def _do_install_blob_pkg(
    config: GlobalConfig,
    mr: MetadataRepo,
    pm: BoundPackageManifest,
    fetch_only: bool,
    reinstall: bool,
) -> int:
    logger = config.logger
    bm = pm.blob_metadata
    assert bm is not None

    pkg_name = pm.name_for_installation
    install_root = config.global_blob_install_root(pkg_name)

    rgs = config.ruyipkg_global_state
    is_installed = rgs.is_package_installed(
        pm.repo_id,
        pm.category,
        pm.name,
        pm.ver,
        "",  # host is "" for blob packages
    )

    # Fallback to directory check if not tracked in state
    if not is_installed and is_root_likely_populated(install_root):
        is_installed = True

    if is_installed:
        if not reinstall:
            logger.I(f"skipping already installed package [green]{pkg_name}[/]")
            return 0

        logger.W(
            f"package [green]{pkg_name}[/] seems already installed; purging and re-installing due to [yellow]--reinstall[/]"
        )
        # Remove from state tracking before purging
        rgs.remove_installation(
            pm.repo_id,
            pm.category,
            pm.name,
            pm.ver,
            "",
        )
        shutil.rmtree(install_root)

    ir_parent = pathlib.Path(install_root).resolve().parent
    ir_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".ruyi-tmp", dir=ir_parent) as tmp_root:
        ret = _do_install_blob_pkg_to(
            config,
            mr,
            pm,
            fetch_only,
            tmp_root,
        )
        if ret != 0:
            return ret
        os.rename(tmp_root, install_root)

    if not fetch_only:
        rgs.record_installation(
            repo_id=pm.repo_id,
            category=pm.category,
            name=pm.name,
            version=pm.ver,
            host="",  # Empty for blob packages
            install_path=install_root,
        )

    logger.I(f"package [green]{pkg_name}[/] installed to [yellow]{install_root}[/]")
    return 0


def _do_install_blob_pkg_to(
    config: GlobalConfig,
    mr: MetadataRepo,
    pm: BoundPackageManifest,
    fetch_only: bool,
    install_root: str,
) -> int:
    logger = config.logger
    bm = pm.blob_metadata
    assert bm is not None

    pkg_name = pm.name_for_installation
    dfs = pm.distfiles
    distfile_names = bm.get_distfile_names()
    if not distfile_names:
        logger.F(f"package [green]{pkg_name}[/] declares no blob distfile")
        return 2

    for df_name in distfile_names:
        df_decl = dfs[df_name]
        ensure_unpack_cmd_for_method(logger, df_decl.unpack_method)
        df = Distfile(df_decl, mr)
        df.ensure(logger)

        if fetch_only:
            logger.D("skipping installation because [yellow]--fetch-only[/] is given")
            continue

        logger.I(f"extracting [green]{df_name}[/] for package [green]{pkg_name}[/]")
        df.unpack_or_symlink(install_root, logger)

    return 0


def do_uninstall_atoms(
    config: GlobalConfig,
    mr: MetadataRepo,
    atom_strs: set[str],
    *,
    canonicalized_host: str | RuyiHost,
    assume_yes: bool,
) -> int:
    logger = config.logger
    logger.D(f"about to uninstall for host {canonicalized_host}: {atom_strs}")

    bis = BoundInstallationStateStore(config.ruyipkg_global_state, mr)

    pms_to_uninstall: list[tuple[str, BoundPackageManifest]] = []
    for a_str in atom_strs:
        a = Atom.parse(a_str)
        pm = a.match_in_repo(bis, config.include_prereleases)
        if pm is None:
            logger.F(f"atom [yellow]{a_str}[/] is non-existent or not installed")
            return 1
        pms_to_uninstall.append((a_str, pm))

    if not pms_to_uninstall:
        logger.I("no packages to uninstall")
        return 0

    logger.I("the following packages will be uninstalled:")
    for _, pm in pms_to_uninstall:
        logger.I(f"  - [green]{pm.category}/{pm.name}[/] ({pm.ver})")

    if not assume_yes:
        if not ask_for_yesno_confirmation(logger, "Proceed?", default=False):
            logger.I("uninstallation aborted")
            return 0

    for a_str, pm in pms_to_uninstall:
        pkg_name = pm.name_for_installation

        if tm := config.telemetry:
            tm.record(
                TelemetryScope(mr.repo_id),
                "repo:package-uninstall-v1",
                atom=a_str,
                host=canonicalized_host,
                pkg_category=pm.category,
                pkg_kinds=pm.kind,
                pkg_name=pm.name,
                pkg_version=pm.ver,
            )

        if pm.binary_metadata is not None:
            ret = _do_uninstall_binary_pkg(
                config,
                pm,
                canonicalized_host,
            )
            if ret != 0:
                return ret
            continue

        if pm.blob_metadata is not None:
            ret = _do_uninstall_blob_pkg(config, pm)
            if ret != 0:
                return ret
            continue

        logger.F(f"don't know how to handle non-binary package [green]{pkg_name}[/]")
        return 2

    return 0


def _do_uninstall_binary_pkg(
    config: GlobalConfig,
    pm: BoundPackageManifest,
    canonicalized_host: str | RuyiHost,
) -> int:
    logger = config.logger
    bm = pm.binary_metadata
    assert bm is not None

    pkg_name = pm.name_for_installation
    install_root = config.global_binary_install_root(str(canonicalized_host), pkg_name)

    rgs = config.ruyipkg_global_state
    is_installed = rgs.is_package_installed(
        pm.repo_id,
        pm.category,
        pm.name,
        pm.ver,
        str(canonicalized_host),
    )

    # Check directory existence if the PM state says the package is not installed
    if not is_installed:
        if not os.path.exists(install_root):
            logger.I(f"skipping not-installed package [green]{pkg_name}[/]")
            return 0

        # There may be potentially user-generated data in the directory,
        # let's be safe and fail the process.
        logger.F(
            f"package [green]{pkg_name}[/] is not tracked as installed, but its directory [yellow]{install_root}[/] exists."
        )
        logger.I("Please remove it manually if you are sure it's safe to do so.")
        logger.I(
            "If you believe this is a bug, please file an issue at [yellow]https://github.com/ruyisdk/ruyi/issues[/]."
        )
        return 1

    logger.I(f"uninstalling package [green]{pkg_name}[/]")
    if is_installed:
        rgs.remove_installation(
            pm.repo_id,
            pm.category,
            pm.name,
            pm.ver,
            str(canonicalized_host),
        )

    if os.path.exists(install_root):
        shutil.rmtree(install_root)

    logger.I(f"package [green]{pkg_name}[/] uninstalled")
    return 0


def _do_uninstall_blob_pkg(
    config: GlobalConfig,
    pm: BoundPackageManifest,
) -> int:
    logger = config.logger
    bm = pm.blob_metadata
    assert bm is not None

    pkg_name = pm.name_for_installation
    install_root = config.global_blob_install_root(pkg_name)

    rgs = config.ruyipkg_global_state
    is_installed = rgs.is_package_installed(
        pm.repo_id,
        pm.category,
        pm.name,
        pm.ver,
        "",  # host is "" for blob packages
    )

    # Check directory existence if the PM state says the package is not installed
    if not is_installed:
        if not os.path.exists(install_root):
            logger.I(f"skipping not-installed package [green]{pkg_name}[/]")
            return 0

        # There may be potentially user-generated data in the directory,
        # let's be safe and fail the process.
        logger.F(
            f"package [green]{pkg_name}[/] is not tracked as installed, but its directory [yellow]{install_root}[/] exists."
        )
        logger.I("Please remove it manually if you are sure it's safe to do so.")
        logger.I(
            "If you believe this is a bug, please file an issue at [yellow]https://github.com/ruyisdk/ruyi/issues[/]."
        )
        return 1

    logger.I(f"uninstalling package [green]{pkg_name}[/]")
    if is_installed:
        rgs.remove_installation(
            pm.repo_id,
            pm.category,
            pm.name,
            pm.ver,
            "",
        )

    if os.path.exists(install_root):
        shutil.rmtree(install_root)

    logger.I(f"package [green]{pkg_name}[/] uninstalled")
    return 0
