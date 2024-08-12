import argparse
import itertools
import os.path
from typing import TypedDict, TypeGuard, cast

import xingque

from .. import log
from ..cli import user_input
from ..config import GlobalConfig
from ..ruyipkg.atom import Atom
from ..ruyipkg.host import get_native_host
from ..ruyipkg.pkg_cli import do_install_atoms
from ..ruyipkg.pkg_manifest import (
    KNOWN_PARTITION_KINDS,
    PartitionKind,
    PartitionMapDecl,
)
from ..ruyipkg.provisioner import (
    DeviceDecl,
    DeviceVariantDecl,
    ImageComboDecl,
    ProvisionerConfig,
)
from ..ruyipkg.repo import MetadataRepo
from ..utils import prereqs


def cli_device_provision(args: argparse.Namespace) -> int:
    try:
        return do_provision_interactive()
    except KeyboardInterrupt:
        log.stdout("\n\nKeyboard interrupt received, exiting.", end="\n\n")
        return 1


def do_provision_interactive() -> int:
    # ensure ruyi repo is present, for good out-of-the-box experience
    config = GlobalConfig.load_from_config()
    mr = MetadataRepo(config)
    mr.ensure_git_repo()

    dpcfg = mr.get_provisioner_config()
    if dpcfg is None:
        log.F("no device provisioner config found in the current Ruyi repository")
        return 1
    cfg_ver = dpcfg["ruyi_provisioner_config"]
    if cfg_ver != "v1":
        log.F(
            f"unknown device provisioner config version '{cfg_ver}', please update [yellow]ruyi[/yellow] and retry"
        )
        return 1

    log.stdout(
        """
[bold green]RuyiSDK Device Provisioning Wizard[/bold green]

This is a wizard intended to help you install a system on your device for your
development pleasure, all with ease.

You will be asked some questions that help RuyiSDK understand your device and
your intended configuration, then packages will be downloaded and flashed onto
the device's storage, that you should somehow make available on this host
system beforehand.

Note that, as Ruyi does not run as [yellow]root[/yellow], but raw disk access is most likely
required to flash images, you should arrange to allow your user account [yellow]sudo[/yellow]
access to necessary commands such as [yellow]dd[/yellow]. Flashing will fail if the [yellow]sudo[/yellow]
configuration does not allow so.
"""
    )

    if not user_input.ask_for_yesno_confirmation("Continue?"):
        log.stdout(
            "\nExiting. You can restart the wizard whenever prepared.",
            end="\n\n",
        )
        return 1

    devices_by_id = {x["id"]: x for x in dpcfg["devices"]}
    img_combos_by_id = {x["id"]: x for x in dpcfg["image_combos"]}

    dev_choices = {k: v["display_name"] for k, v in devices_by_id.items()}
    dev_id = user_input.ask_for_kv_choice(
        "\nThe following devices are currently supported by the wizard. Please pick your device:",
        dev_choices,
    )
    dev = devices_by_id[dev_id]

    variant_choices = [i["display_name"] for i in dev["variants"]]
    variant_idx = user_input.ask_for_choice(
        "\nThe device has the following variants. Please choose the one corresponding to your hardware at hand:",
        variant_choices,
    )
    variant = dev["variants"][variant_idx]

    combo_choices = {
        combo_id: img_combos_by_id[combo_id]["display_name"]
        for combo_id in variant["supported_combos"]
    }
    combo_id = user_input.ask_for_kv_choice(
        "\nThe following system configurations are supported by the device variant you have chosen. Please pick the one you want to put on the device:",
        combo_choices,
    )
    combo = img_combos_by_id[combo_id]

    return do_provision_combo_interactive(config, dpcfg, mr, dev, variant, combo)


def do_provision_combo_interactive(
    config: GlobalConfig,
    dpcfg: ProvisionerConfig,
    mr: MetadataRepo,
    dev_decl: DeviceDecl,
    variant_decl: DeviceVariantDecl,
    combo: ImageComboDecl,
) -> int:
    log.D(f"provisioning device variant '{dev_decl['id']}@{variant_decl['id']}'")

    # download packages
    pkg_atoms = combo["packages"]
    if not pkg_atoms:
        if postinst_msgid := combo.get("postinst_msgid"):
            if postinst_msgs := dpcfg.get("postinst_messages"):
                postinst_msg = postinst_msgs[postinst_msgid]
                log.stdout(f"\n{postinst_msg}")
                return 0

        log.F(
            f"malformed config: device variant '{dev_decl['id']}@{variant_decl['id']}' asks for no packages but provides no messages either"
        )
        return 1

    pkg_names_for_display = "\n".join(f" * [green]{i}[/green]" for i in pkg_atoms)
    log.stdout(
        f"""
We are about to download and install the following packages for your device:

{pkg_names_for_display}
"""
    )
    if not user_input.ask_for_yesno_confirmation("Proceed?"):
        log.stdout("\nExiting. You may restart the wizard at any time.", end="\n\n")
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
        log.F("failed to download and install packages")
        log.I("your device was not touched")
        return 2

    strat_provider = ProvisionStrategyProvider(mr)
    strategies = [
        (pkg, get_pkg_provision_strategy(strat_provider, mr, pkg)) for pkg in pkg_atoms
    ]
    strategies.sort(key=lambda x: x[1].priority, reverse=True)

    # compose a partition map for each image pkg installed
    pkg_part_maps = {pkg: make_pkg_part_map(config, mr, pkg) for pkg in pkg_atoms}
    all_parts = list(
        set(
            itertools.chain(
                *(pkg_part_map.keys() for pkg_part_map in pkg_part_maps.values())
            )
        )
    )

    # prompt user to give paths to target block device(s)
    requested_host_blkdevs = set(
        itertools.chain(
            *(strat[1].need_host_blkdevs(all_parts) for strat in strategies)
        )
    )
    host_blkdev_map: PartitionMapDecl = {}
    if requested_host_blkdevs:
        log.stdout(
            """
For initializing this target device, you should plug into this host system the
device's storage (e.g. SD card or NVMe SSD), or a removable disk to be
reformatted as a live medium, and note down the corresponding device file
path(s), e.g. /dev/sdX, /dev/nvmeXnY for whole disks; /dev/sdXY, /dev/nvmeXnYpZ
for partitions. You may consult e.g. [yellow]sudo blkid[/yellow] output for the
information you will need later.
"""
        )
        for part in requested_host_blkdevs:
            part_desc = get_part_desc(part)
            path = user_input.ask_for_file(f"Please give the path for the {part_desc}:")
            host_blkdev_map[part] = path

    # final confirmation
    log.stdout(
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
    log.stdout(pretend_steps, end="\n\n")

    if not user_input.ask_for_yesno_confirmation("Proceed with flashing?"):
        log.stdout(
            "\nExiting. The device is not touched and you may re-start the wizard at will.",
            end="\n\n",
        )
        return 1

    # ensure commands
    all_needed_cmds = set(itertools.chain(*(strat.need_cmd for _, strat in strategies)))
    if all_needed_cmds:
        prereqs.ensure_cmds(*all_needed_cmds)

        if "fastboot" in all_needed_cmds:
            # ask the user to ensure the device shows up
            # TODO: automate doing so
            log.stdout(
                """
Some flashing steps require the use of fastboot, in which case you should
ensure the target device is showing up in [yellow]fastboot devices[/yellow] output.
Please confirm it yourself before the flashing begins.
"""
            )
            if not user_input.ask_for_yesno_confirmation(
                "Is the device identified by fastboot now?"
            ):
                log.stdout(
                    "\nAborting. The device is not touched. You may re-start the wizard after [yellow]fastboot[/yellow] is fixed for the device.",
                    end="\n\n",
                )
                return 1

    # flash
    for pkg, strat in strategies:
        log.D(f"flashing {pkg} with strategy {strat}")
        ret = strat.flash(pkg_part_maps[pkg], host_blkdev_map)
        if ret != 0:
            log.F("flashing failed, check your device right now")
            return ret

    # parting words
    log.stdout(
        """
It seems the flashing has finished without errors.

[bold green]Happy hacking![/bold green]
"""
    )

    if postinst_msgid := combo.get("postinst_msgid"):
        if postinst_msgs := dpcfg.get("postinst_messages"):
            postinst_msg = postinst_msgs[postinst_msgid]
            log.stdout(f"\n{postinst_msg}")

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
    need_host_blkdevs_fn: (
        xingque.Value
    )  # Callable[[list[PartitionKind]], list[PartitionKind]]
    need_cmd: list[str]
    pretend_fn: (
        xingque.Value
    )  # Callable[[PartitionMapDecl, PartitionMapDecl], list[str]]
    flash_fn: xingque.Value  # Callable[[PartitionMapDecl, PartitionMapDecl], int]


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
    def __init__(self, decl: PackageProvisionStrategyDecl) -> None:
        self._d = decl

    @property
    def priority(self) -> int:
        return self._d["priority"]

    @property
    def need_cmd(self) -> list[str]:
        return self._d["need_cmd"]

    def need_host_blkdevs(self, x: list[PartitionKind]) -> list[PartitionKind]:
        ev = xingque.Evaluator()
        result = ev.eval_function(self._d["need_host_blkdevs_fn"], x)
        if not validate_list_partition_kinds(result):
            raise TypeError("need_host_blkdevs_fn must return list[PartitionKind]")
        return result

    def pretend(
        self,
        img_paths: PartitionMapDecl,
        blkdev_paths: PartitionMapDecl,
    ) -> list[str]:
        ev = xingque.Evaluator()
        result = ev.eval_function(self._d["pretend_fn"], img_paths, blkdev_paths)
        if not validate_list_str(result):
            raise TypeError("pretend_fn must return list[str]")
        return result

    def flash(
        self,
        img_paths: PartitionMapDecl,
        blkdev_paths: PartitionMapDecl,
    ) -> int:
        ev = xingque.Evaluator()
        result = ev.eval_function(self._d["flash_fn"], img_paths, blkdev_paths)
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
            self._strats[name] = PackageProvisionStrategy(decl)

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
