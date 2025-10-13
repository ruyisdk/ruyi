import itertools
import os.path
from typing import TYPE_CHECKING, TypedDict, TypeGuard, cast

from ..cli import user_input
from ..config import GlobalConfig
from ..log import RuyiLogger
from ..ruyipkg.atom import Atom, ExprAtom, SlugAtom
from ..ruyipkg.entity_provider import BaseEntity
from ..ruyipkg.host import get_native_host
from ..ruyipkg.install import do_install_atoms
from ..ruyipkg.pkg_manifest import (
    KNOWN_PARTITION_KINDS,
    PartitionKind,
    PartitionMapDecl,
)
from ..ruyipkg.repo import MetadataRepo
from ..utils import mounts, prereqs

if TYPE_CHECKING:
    from ..ruyipkg.pkg_manifest import BoundPackageManifest


def get_variant_display_name(dev: BaseEntity, variant: BaseEntity) -> str:
    """Get the display name of a device variant."""
    if n := variant.display_name:
        return n
    return f"{dev.display_name} ({variant.data['variant_name']})"


def do_provision_interactive(config: GlobalConfig) -> int:
    log = config.logger

    # ensure ruyi repo is present, for good out-of-the-box experience
    mr = config.repo
    mr.ensure_git_repo()

    log.stdout(
        """
[bold green]RuyiSDK Device Provisioning Wizard[/]

This is a wizard intended to help you install a system on your device for your
development pleasure, all with ease.

You will be asked some questions that help RuyiSDK understand your device and
your intended configuration, then packages will be downloaded and flashed onto
the device's storage, that you should somehow make available on this host
system beforehand.

Note that, as Ruyi does not run as [yellow]root[/], but raw disk access is most likely
required to flash images, you should arrange to allow your user account [yellow]sudo[/]
access to necessary commands such as [yellow]dd[/]. Flashing will fail if the [yellow]sudo[/]
configuration does not allow so.
"""
    )

    if not user_input.ask_for_yesno_confirmation(log, "Continue?"):
        log.stdout(
            "\nExiting. You can restart the wizard whenever prepared.",
            end="\n\n",
        )
        return 1

    device_entities = list(mr.entity_store.iter_entities("device"))
    device_entities.sort(key=lambda x: x.display_name or "")
    devices_by_id = {x.id: x for x in device_entities}

    dev_choices = {k: v.display_name or "" for k, v in devices_by_id.items()}
    dev_id = user_input.ask_for_kv_choice(
        log,
        "\nThe following devices are currently supported by the wizard. Please pick your device:",
        dev_choices,
    )
    dev = devices_by_id[dev_id]

    variants = list(
        mr.entity_store.traverse_related_entities(
            dev,
            entity_types=["device-variant"],
        )
    )
    variants.sort(key=lambda x: x.data.get("variant_name", ""))

    variant_choices = [get_variant_display_name(dev, i) for i in variants]
    variant_idx = user_input.ask_for_choice(
        log,
        "\nThe device has the following variants. Please choose the one corresponding to your hardware at hand:",
        variant_choices,
    )
    variant = variants[variant_idx]

    supported_combos = list(
        mr.entity_store.traverse_related_entities(
            variant,
            forward_refs=False,
            reverse_refs=True,
            entity_types=["image-combo"],
        )
    )
    supported_combos.sort(key=lambda x: x.display_name or "")
    combo_choices = [combo.display_name or "" for combo in supported_combos]
    combo_idx = user_input.ask_for_choice(
        log,
        "\nThe following system configurations are supported by the device variant you have chosen. Please pick the one you want to put on the device:",
        combo_choices,
    )
    combo = supported_combos[combo_idx]

    return do_provision_combo_interactive(config, mr, dev, variant, combo)


def maybe_render_postinst_msg(
    logger: RuyiLogger,
    mr: MetadataRepo,
    combo: BaseEntity,
    lang_code: str,
) -> bool:
    if postinst_msgid := combo.data.get("postinst_msgid"):
        # This field is named just "msgid" so no variables to render for
        # the retrieved text
        if msg := mr.messages.get_message_template(postinst_msgid, lang_code):
            logger.stdout(f"\n{msg}")
            return True
    return False


def do_provision_combo_interactive(
    config: GlobalConfig,
    mr: MetadataRepo,
    dev_decl: BaseEntity,
    variant_decl: BaseEntity,
    combo: BaseEntity,
) -> int:
    logger = config.logger
    logger.D(f"provisioning device variant '{dev_decl.id}@{variant_decl.id}'")

    # download packages
    pkg_atoms = combo.data.get("package_atoms", [])
    if not pkg_atoms:
        if maybe_render_postinst_msg(logger, mr, combo, config.lang_code):
            return 0

        logger.F(
            f"malformed config: device variant '{dev_decl.id}@{variant_decl.id}' asks for no packages but provides no messages either"
        )
        return 1

    new_pkg_atoms = customize_package_versions(config, mr, pkg_atoms)
    if new_pkg_atoms is None:
        logger.stdout("\nExiting. You may restart the wizard at any time.", end="\n\n")
        return 1
    else:
        pkg_atoms = new_pkg_atoms

    pkg_names_for_display = "\n".join(f" * [green]{i}[/]" for i in pkg_atoms)
    logger.stdout(
        f"""
We are about to download and install the following packages for your device:

{pkg_names_for_display}
"""
    )

    if not user_input.ask_for_yesno_confirmation(logger, "Proceed?"):
        logger.stdout("\nExiting. You may restart the wizard at any time.", end="\n\n")
        return 1

    ret = do_install_atoms(
        config,
        mr,
        set(pkg_atoms),
        canonicalized_host=get_native_host(),
        fetch_only=False,
        reinstall=False,
    )
    if ret != 0:
        logger.F("failed to download and install packages")
        logger.I("your device was not touched")
        return 2

    strat_provider = ProvisionStrategyProvider(mr)
    strategies = [
        (pkg, get_pkg_provision_strategy(strat_provider, mr, pkg)) for pkg in pkg_atoms
    ]
    strategies.sort(key=lambda x: x[1].priority, reverse=True)

    # compose a partition map for each image pkg installed
    pkg_part_maps = {pkg: make_pkg_part_map(config, mr, pkg) for pkg in pkg_atoms}
    all_parts: list[PartitionKind] = []
    for pkg_part_map in pkg_part_maps.values():
        all_parts.extend(pkg_part_map.keys())

    # prompt user to give paths to target block device(s)
    requested_host_blkdevs: list[PartitionKind] = []
    for pkg, strat in strategies:
        requested_host_blkdevs.extend(strat.need_host_blkdevs(all_parts))

    host_blkdev_map: PartitionMapDecl = {}
    if requested_host_blkdevs:
        logger.stdout(
            """
For initializing this target device, you should plug into this host system the
device's storage (e.g. SD card or NVMe SSD), or a removable disk to be
reformatted as a live medium, and note down the corresponding device file
path(s), e.g. /dev/sdX, /dev/nvmeXnY for whole disks; /dev/sdXY, /dev/nvmeXnYpZ
for partitions. You may consult e.g. [yellow]sudo blkid[/] output for the
information you will need later.
"""
        )
        for part in requested_host_blkdevs:
            part_desc = get_part_desc(part)

            while True:
                path = user_input.ask_for_file(
                    logger,
                    f"Please give the path for the {part_desc}:",
                )

                # Retrieve the latest mount info in case the user un-mounts
                # on seeing the prompt
                all_mounts = mounts.parse_mounts()
                blkdev_mounts = [m for m in all_mounts if m.source_is_blkdev]
                path_valid = True
                for m in blkdev_mounts:
                    if m.source_path.samefile(path):
                        logger.W(
                            f"path [cyan]'{path}'[/] is currently mounted at [yellow]'{m.target}'[/]"
                        )
                        logger.I(
                            "rejecting the path for safety; please double-check and retry"
                        )
                        path_valid = False
                        break
                if path_valid:
                    break

            host_blkdev_map[part] = path

    # final confirmation
    logger.stdout(
        """
We have collected enough information for the actual flashing. Now is the last
chance to re-check and confirm everything is fine.

We are about to:
"""
    )

    pretend_steps = "\n".join(
        f" * {step_str}"
        for step_str in itertools.chain(
            *(
                strat[1].pretend(pkg_part_maps[strat[0]], host_blkdev_map)
                for strat in strategies
            )
        )
    )
    logger.stdout(pretend_steps, end="\n\n")

    if not user_input.ask_for_yesno_confirmation(logger, "Proceed with flashing?"):
        logger.stdout(
            "\nExiting. The device is not touched and you may re-start the wizard at will.",
            end="\n\n",
        )
        return 1

    # ensure commands
    all_needed_cmds = set(itertools.chain(*(strat.need_cmd for _, strat in strategies)))
    if all_needed_cmds:
        prereqs.ensure_cmds(logger, all_needed_cmds, interactive_retry=True)

        if "fastboot" in all_needed_cmds:
            # ask the user to ensure the device shows up
            # TODO: automate doing so
            logger.stdout(
                """
Some flashing steps require the use of fastboot, in which case you should
ensure the target device is showing up in [yellow]fastboot devices[/] output.
Please [bold red]confirm it yourself before continuing[/].
"""
            )
            if not user_input.ask_for_yesno_confirmation(
                logger,
                "Is the device identified by fastboot now?",
            ):
                logger.stdout(
                    "\nAborting. The device is not touched. You may re-start the wizard after [yellow]fastboot[/] is fixed for the device.",
                    end="\n\n",
                )
                return 1

    # flash
    for pkg, strat in strategies:
        logger.D(f"flashing {pkg} with strategy {strat}")
        ret = strat.flash(pkg_part_maps[pkg], host_blkdev_map)
        if ret != 0:
            logger.F("flashing failed, check your device right now")
            return ret

    # parting words
    logger.stdout(
        """
It seems the flashing has finished without errors.

[bold green]Happy hacking![/]
"""
    )

    maybe_render_postinst_msg(logger, mr, combo, config.lang_code)

    return 0


def get_part_desc(part: PartitionKind) -> str:
    match part:
        case "disk":
            return "target's whole disk"
        case "live":
            return "removable disk to use as live medium"
        case _:
            return f"target's '{part}' partition"


class PackageProvisionStrategyDecl(TypedDict):
    priority: int  # higher number means earlier
    need_host_blkdevs_fn: object  # Callable[[list[PartitionKind]], list[PartitionKind]]
    need_cmd: list[str]
    pretend_fn: object  # Callable[[PartitionMapDecl, PartitionMapDecl], list[str]]
    flash_fn: object  # Callable[[PartitionMapDecl, PartitionMapDecl], int]


def validate_list_str(x: object) -> TypeGuard[list[str]]:
    if not isinstance(x, list):
        return False
    x = cast(list[object], x)
    return all(isinstance(y, str) for y in x)


def validate_list_partition_kinds(x: object) -> TypeGuard[list[PartitionKind]]:
    if not isinstance(x, list):
        return False
    x = cast(list[object], x)
    for item in x:
        if not isinstance(item, str) or item not in KNOWN_PARTITION_KINDS:
            return False
    return True


class PackageProvisionStrategy:
    def __init__(
        self,
        decl: PackageProvisionStrategyDecl,
        mr: MetadataRepo,
    ) -> None:
        self._d = decl
        self._mr = mr

    @property
    def priority(self) -> int:
        return self._d["priority"]

    @property
    def need_cmd(self) -> list[str]:
        return self._d["need_cmd"]

    def need_host_blkdevs(self, x: list[PartitionKind]) -> list[PartitionKind]:
        result = self._mr.eval_plugin_fn(self._d["need_host_blkdevs_fn"], x)
        if not validate_list_partition_kinds(result):
            raise TypeError("need_host_blkdevs_fn must return list[PartitionKind]")
        return result

    def pretend(
        self,
        img_paths: PartitionMapDecl,
        blkdev_paths: PartitionMapDecl,
    ) -> list[str]:
        result = self._mr.eval_plugin_fn(self._d["pretend_fn"], img_paths, blkdev_paths)
        if not validate_list_str(result):
            raise TypeError("pretend_fn must return list[str]")
        return result

    def flash(
        self,
        img_paths: PartitionMapDecl,
        blkdev_paths: PartitionMapDecl,
    ) -> int:
        result = self._mr.eval_plugin_fn(self._d["flash_fn"], img_paths, blkdev_paths)
        if not isinstance(result, int):
            raise TypeError("flash_fn must return int")
        return result


class ProvisionStrategyProvider:
    def __init__(self, mr: MetadataRepo) -> None:
        self._mr = mr
        self._strats: dict[str, PackageProvisionStrategy] = {}

        # import the "standard library" of strategies
        self._import_strategy_plugin("std")

    def _import_strategy_plugin(self, plugin_pkg_name: str) -> None:
        plugin_id = f"ruyi-device-provision-strategy-{plugin_pkg_name}"
        provided_strats = self._mr.get_from_plugin(
            plugin_id,
            "PROVIDED_DEVICE_PROVISION_STRATEGIES_V1",
        )
        if not isinstance(provided_strats, dict):
            raise RuntimeError(
                f"malformed device provisioner strategy plugin '{plugin_id}'"
            )
        for name, decl in provided_strats.items():
            self._strats[name] = PackageProvisionStrategy(decl, self._mr)

    def __getitem__(self, name: str) -> PackageProvisionStrategy:
        try:
            return self._strats[name]
        except KeyError:
            # for now it's "ruyi-device-provision-strategy-STRATEGY-NAME"
            # we may have to revise before Ruyi v1.0 though
            self._import_strategy_plugin(name)
            return self._strats[name]


def get_pkg_provision_strategy(
    strat_provider: ProvisionStrategyProvider,
    mr: MetadataRepo,
    atom: str,
) -> PackageProvisionStrategy:
    a = Atom.parse(atom)
    pm = a.match_in_repo(mr, True)
    assert pm is not None

    pmd = pm.provisionable_metadata
    assert pmd is not None
    return strat_provider[pmd.strategy]


def make_pkg_part_map(
    config: GlobalConfig,
    mr: MetadataRepo,
    atom: str,
) -> PartitionMapDecl:
    a = Atom.parse(atom)
    pm = a.match_in_repo(mr, True)
    assert pm is not None
    pkg_root = config.global_blob_install_root(pm.name_for_installation)

    pmd = pm.provisionable_metadata
    assert pmd is not None
    return {p: os.path.join(pkg_root, f) for p, f in pmd.partition_map.items()}


def is_package_version_customization_possible(
    gc: GlobalConfig,
    mr: MetadataRepo,
    pkg_atoms: list[str],
) -> bool:
    """
    Check if package version customization is possible, which means there
    are at least one package atom specified that matches more than one versions.
    """

    for atom_str in pkg_atoms:
        # Get all available versions for this package
        a = Atom.parse(atom_str)
        try:
            if len(list(a.iter_in_repo(mr, gc.include_prereleases))) > 1:
                return True
        except KeyError:
            continue

    return False


def customize_package_versions(
    config: GlobalConfig,
    mr: MetadataRepo,
    pkg_atoms: list[str],
) -> list[str] | None:
    """
    Allow the user to customize the versions of packages to be installed.
    Returns a new list of package atoms with user-selected versions.
    """

    if not is_package_version_customization_possible(config, mr, pkg_atoms):
        return pkg_atoms

    logger = config.logger

    # Ask if the user wants to customize package versions
    logger.stdout(
        "By default, we'll install the latest version of each package, but in this case, other choices are possible."
    )
    if not user_input.ask_for_yesno_confirmation(
        logger,
        "Would you like to customize package versions?",
    ):
        return pkg_atoms

    while True:  # Loop to allow restarting the selection process
        result: list[str] = []
        logger.stdout("\n[bold]Package Version Selection[/]")

        for atom_str in pkg_atoms:
            # Parse the atom to get package name
            a = Atom.parse(atom_str)
            if isinstance(a, ExprAtom):
                # If it's already an expression with version constraints, show the constraints
                logger.stdout(
                    f"\nPackage [green]{atom_str}[/] already has version constraints."
                )
                if not user_input.ask_for_yesno_confirmation(
                    logger,
                    "Would you like to change them?",
                ):
                    result.append(atom_str)
                    continue
            elif isinstance(a, SlugAtom):
                # Slugs already fix the version, so we can't change them
                logger.W(
                    f"version cannot be overridden for slug atom [green]{atom_str}[/]"
                )
                result.append(atom_str)
                continue

            # Get all available versions for this package
            package_name = a.name
            category = a.category

            available_versions: "list[BoundPackageManifest]" = []
            try:
                available_versions = list(mr.iter_pkg_vers(package_name, category))
            except KeyError:
                logger.W(
                    f"could not find package [yellow]{category}/{package_name}[/] in repository"
                )
                result.append(atom_str)

            if not available_versions:
                logger.W(
                    f"no versions found for package [yellow]{category}/{package_name}[/]"
                )
                result.append(atom_str)
                continue

            if len(available_versions) == 1:
                # If there's only one version available, use it
                selected_version = available_versions[0]
                logger.stdout(
                    f"Only one version available for [green]{category}/{package_name}[/]: [blue]{selected_version.ver}[/], using it."
                )
                result.append(atom_str)
                continue

            # Sort versions with newest first
            available_versions.sort(key=lambda pm: pm.semver, reverse=True)

            # Create a list of version choices for display
            version_choices = []
            for pm in available_versions:
                version_str = str(pm.semver)
                remarks = []

                if pm.is_prerelease:
                    remarks.append("prerelease")
                if pm.service_level.has_known_issues:
                    remarks.append("has known issues")
                if pm.upstream_version:
                    remarks.append(f"upstream: {pm.upstream_version}")

                remark_str = f" ({', '.join(remarks)})" if remarks else ""
                version_choices.append(f"{version_str}{remark_str}")

            # Ask the user to select a version
            version_idx = user_input.ask_for_choice(
                logger,
                f"\nSelect a version for package [green]{category or ''}{('/' + package_name) if category else package_name}[/]:",
                version_choices,
            )

            selected_version = available_versions[version_idx]

            # Create the new atom string with the selected version
            if category:
                new_atom = f"{category}/{package_name}(=={selected_version.ver})"
            else:
                new_atom = f"{package_name}(=={selected_version.ver})"

            logger.stdout(f"Selected: [blue]{new_atom}[/]")
            result.append(new_atom)

        logger.stdout("\nPackage versions to be installed:")
        for atom in result:
            logger.stdout(f" * [green]{atom}[/]")

        confirmation = user_input.ask_for_choice(
            logger,
            "\nHow would you like to proceed?",
            [
                "Continue with these versions",
                "Restart version selection",
                "Abort device provisioning",
            ],
        )

        if confirmation == 0:  # Continue with these versions
            return result
        elif confirmation == 1:  # Restart version selection
            logger.stdout("\nRestarting package version selection...")
            continue
        else:  # Abort installation
            return None
