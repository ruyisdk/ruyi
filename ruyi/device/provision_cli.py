import argparse
import itertools
import os.path
import platform
import subprocess
import time
from typing import Callable, NotRequired, TypedDict

from .. import log
from ..cli import prereqs, user_input
from ..config import GlobalConfig
from ..ruyipkg.atom import Atom
from ..ruyipkg.pkg_cli import do_install_atoms
from ..ruyipkg.pkg_manifest import PartitionKind, PartitionMapDecl
from ..ruyipkg.repo import MetadataRepo


class ImageComboDecl(TypedDict):
    id: str
    display_name: str
    packages: list[str]
    postinst_fn: NotRequired[Callable[[], None]]


def postinst_oerv_on_milkv_pioneer_nvme_models() -> None:
    log.stdout(
        """
[bold green]NOTE[/bold green]: You will need to tweak the rootfs parameter for openEuler to properly
boot on Milk-V Pioneer v1.2 and later models, whose rootfs resides on NVMe
drive instead of TF card.

Since [yellow]ruyi[/yellow] does not run as [yellow]root[/yellow], you will have to perform the following
actions yourself before booting the target device:

* mount the target device's [green]/boot[/green] partition,
* check the file [cyan]/extlinux/extlinux.conf[/cyan] in the partition,
* replace [yellow]mmcblk1p3[/yellow] with [yellow]nvme0n1p3[/yellow] as needed.
"""
    )


IMAGE_COMBOS: list[ImageComboDecl] = [
    {
        "id": "buildroot-sdk-milkv-duo",
        "display_name": "Milk-V Duo Official buildroot SDK (64M RAM)",
        "packages": [
            "board-image/buildroot-sdk-milkv-duo",
        ],
    },
    {
        "id": "buildroot-sdk-milkv-duo-python",
        "display_name": "Milk-V Duo Official buildroot SDK (64M RAM, with Python)",
        "packages": [
            "board-image/buildroot-sdk-milkv-duo-python",
        ],
    },
    {
        "id": "buildroot-sdk-milkv-duo256m",
        "display_name": "Milk-V Duo Official buildroot SDK (256M RAM)",
        "packages": [
            "board-image/buildroot-sdk-milkv-duo256m",
        ],
    },
    {
        "id": "buildroot-sdk-milkv-duo256m-python",
        "display_name": "Milk-V Duo Official buildroot SDK (256M RAM, with Python)",
        "packages": [
            "board-image/buildroot-sdk-milkv-duo256m-python",
        ],
    },
    {
        "id": "oerv-milkv-pioneer-base",
        "display_name": "openEuler RISC-V (base system) for Milk-V Pioneer",
        "packages": [
            "board-image/oerv-sg2042-milkv-pioneer-base",
        ],
    },
    {
        "id": "oerv-milkv-pioneer-xfce",
        "display_name": "openEuler RISC-V (XFCE) for Milk-V Pioneer",
        "packages": [
            "board-image/oerv-sg2042-milkv-pioneer-xfce",
        ],
    },
    {
        "id": "oerv-milkv-pioneer-base-nvme",
        "display_name": "openEuler RISC-V (base system) for Milk-V Pioneer (rootfs on NVMe)",
        "packages": [
            "board-image/oerv-sg2042-milkv-pioneer-base",
        ],
        "postinst_fn": postinst_oerv_on_milkv_pioneer_nvme_models,
    },
    {
        "id": "oerv-milkv-pioneer-xfce-nvme",
        "display_name": "openEuler RISC-V (XFCE) for Milk-V Pioneer (rootfs on NVMe)",
        "packages": [
            "board-image/oerv-sg2042-milkv-pioneer-xfce",
        ],
        "postinst_fn": postinst_oerv_on_milkv_pioneer_nvme_models,
    },
    {
        "id": "oerv-sipeed-lpi4a-8g-headless",
        "display_name": "openEuler RISC-V (headless) for Sipeed LicheePi 4A (8G RAM)",
        "packages": [
            "board-image/oerv-sipeed-lpi4a-headless",
            "board-image/uboot-oerv-sipeed-lpi4a-8g",
        ],
    },
    {
        "id": "oerv-sipeed-lpi4a-8g-xfce",
        "display_name": "openEuler RISC-V (XFCE) for Sipeed LicheePi 4A (8G RAM)",
        "packages": [
            "board-image/oerv-sipeed-lpi4a-xfce",
            "board-image/uboot-oerv-sipeed-lpi4a-8g",
        ],
    },
    {
        "id": "oerv-sipeed-lpi4a-16g-headless",
        "display_name": "openEuler RISC-V (headless) for Sipeed LicheePi 4A (16G RAM)",
        "packages": [
            "board-image/oerv-sipeed-lpi4a-headless",
            "board-image/uboot-oerv-sipeed-lpi4a-16g",
        ],
    },
    {
        "id": "oerv-sipeed-lpi4a-16g-xfce",
        "display_name": "openEuler RISC-V (XFCE) for Sipeed LicheePi 4A (16G RAM)",
        "packages": [
            "board-image/oerv-sipeed-lpi4a-xfce",
            "board-image/uboot-oerv-sipeed-lpi4a-16g",
        ],
    },
    {
        "id": "revyos-milkv-pioneer",
        "display_name": "RevyOS for Milk-V Pioneer",
        "packages": [
            "board-image/revyos-sg2042-milkv-pioneer",
        ],
    },
    {
        "id": "revyos-sipeed-lpi4a-8g",
        "display_name": "RevyOS for Sipeed LicheePi 4A (8G RAM)",
        "packages": [
            "board-image/revyos-sipeed-lpi4a",
            "board-image/uboot-revyos-sipeed-lpi4a-8g",
        ],
    },
    {
        "id": "revyos-sipeed-lpi4a-16g",
        "display_name": "RevyOS for Sipeed LicheePi 4A (16G RAM)",
        "packages": [
            "board-image/revyos-sipeed-lpi4a",
            "board-image/uboot-revyos-sipeed-lpi4a-16g",
        ],
    },
]


class DeviceVariantDecl(TypedDict):
    id: str
    display_name: str
    supported_combos: list[str]


class DeviceDecl(TypedDict):
    id: str
    display_name: str
    variants: list[DeviceVariantDecl]


DEVICE_MILKV_DUO: DeviceDecl = {
    "id": "milkv-duo",
    "display_name": "Milk-V Duo",
    "variants": [
        {
            "id": "64m",
            "display_name": "Milk-V Duo (64M RAM)",
            "supported_combos": [
                "buildroot-sdk-milkv-duo",
                "buildroot-sdk-milkv-duo-python",
            ],
        },
        {
            "id": "256m",
            "display_name": "Milk-V Duo (256M RAM)",
            "supported_combos": [
                "buildroot-sdk-milkv-duo256m",
                "buildroot-sdk-milkv-duo256m-python",
            ],
        },
    ],
}

DEVICE_MILKV_PIONEER: DeviceDecl = {
    "id": "milkv-pioneer",
    "display_name": "Milk-V Pioneer Box",
    "variants": [
        {
            "id": "v1.3",
            "display_name": "Milk-V Pioneer Box (v1.3)",
            "supported_combos": [
                # "fedora-milkv-pioneer-v1.2"  # cannot download from Google Drive
                "oerv-milkv-pioneer-base-nvme",
                "oerv-milkv-pioneer-xfce-nvme",
                "revyos-milkv-pioneer",
            ],
        },
        {
            "id": "v1.2",
            "display_name": "Milk-V Pioneer Box (v1.2)",
            "supported_combos": [
                # "fedora-milkv-pioneer-v1.2"  # cannot download from Google Drive
                "oerv-milkv-pioneer-base-nvme",
                "oerv-milkv-pioneer-xfce-nvme",
                # "revyos-milkv-pioneer",  # not indicated by PM
            ],
        },
        {
            "id": "v1.1",
            "display_name": "Milk-V Pioneer Box (v1.1)",
            "supported_combos": [
                # "fedora-milkv-pioneer-v1.1"  # cannot download from Google Drive
                "oerv-milkv-pioneer-base",
                "oerv-milkv-pioneer-xfce",
                # "revyos-milkv-pioneer",  # not indicated by PM
            ],
        },
    ],
}

DEVICE_SIPEED_LPI4A: DeviceDecl = {
    "id": "sipeed-lpi4a",
    "display_name": "Sipeed LicheePi 4A",
    "variants": [
        {
            "id": "8g",
            "display_name": "Sipeed LicheePi 4A (8G RAM)",
            "supported_combos": [
                "oerv-sipeed-lpi4a-8g-headless",
                "oerv-sipeed-lpi4a-8g-xfce",
                "revyos-sipeed-lpi4a-8g",
            ],
        },
        {
            "id": "16g",
            "display_name": "Sipeed LicheePi 4A (16G RAM)",
            "supported_combos": [
                "oerv-sipeed-lpi4a-16g-headless",
                "oerv-sipeed-lpi4a-16g-xfce",
                "revyos-sipeed-lpi4a-16g",
            ],
        },
    ],
}

DEVICES: list[DeviceDecl] = [
    DEVICE_MILKV_DUO,
    DEVICE_MILKV_PIONEER,
    DEVICE_SIPEED_LPI4A,
]


def cli_device_provision(args: argparse.Namespace) -> int:
    try:
        return do_provision_interactive()
    except KeyboardInterrupt:
        log.stdout("\n\nKeyboard interrupt received, exiting.", end="\n\n")
        return 1


def do_provision_interactive() -> int:
    # ensure ruyi repo is present, for good out-of-the-box experience
    config = GlobalConfig.load_from_config()
    mr = MetadataRepo(
        config.get_repo_dir(),
        config.get_repo_url(),
        config.get_repo_branch(),
    )
    mr.ensure_git_repo()

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

    devices_by_id = {x["id"]: x for x in DEVICES}
    img_combos_by_id = {x["id"]: x for x in IMAGE_COMBOS}

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

    return do_provision_combo_interactive(config, mr, dev, variant, combo)


def do_provision_combo_interactive(
    config: GlobalConfig,
    mr: MetadataRepo,
    dev_decl: DeviceDecl,
    variant_decl: DeviceVariantDecl,
    combo: ImageComboDecl,
) -> int:
    log.D(f"provisioning device variant '{dev_decl['id']}@{variant_decl['id']}'")

    # download packages
    pkg_atoms = combo["packages"]
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
        host=platform.machine(),
        fetch_only=False,
        reinstall=False,
    )
    if ret != 0:
        log.F("failed to download and install packages")
        log.I("your device was not touched")
        return 2

    # this is hacky: currently correspondence is manually ensured
    strategies = [(pkg, PKG_PROVISION_STRATEGY[pkg]) for pkg in pkg_atoms]
    strategies.sort(key=lambda x: x[1]["priority"], reverse=True)

    # compose a partition map for each image pkg installed
    # XXX: the data is also hard-coded for now, pending proper integration into
    # the repo
    pkg_part_maps = {pkg: make_pkg_part_map(config, mr, pkg) for pkg in pkg_atoms}

    # prompt user to give paths to target block device(s)
    requested_host_blkdevs = set(
        itertools.chain(*(strat[1]["need_host_blkdevs"] for strat in strategies))
    )
    host_blkdev_map: PartitionMapDecl = {}
    if requested_host_blkdevs:
        log.stdout(
            """
For initializing this target device, you should plug the device's storage (e.g.
SD card or NVMe SSD) into this host system, and note down the corresponding
device file path(s), e.g. /dev/sdX, /dev/nvmeXnY for whole disks; /dev/sdXY,
/dev/nvmeXnYpZ for partitions. You may consult e.g. [yellow]sudo blkid[/yellow] output
for the information you will need later.
"""
        )
        for part in requested_host_blkdevs:
            part_desc = "whole disk" if part == "disk" else f"'{part}' partition"
            path = user_input.ask_for_file(
                f"Please give the path for the target's {part_desc}:"
            )
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
                strat[1]["pretend_fn"](pkg_part_maps[strat[0]], host_blkdev_map)
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
    all_needed_cmds = set(
        itertools.chain(*(strat["need_cmd"] for _, strat in strategies))
    )
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
        ret = strat["flash_fn"](pkg_part_maps[pkg], host_blkdev_map)
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

    if postinst_fn := combo.get("postinst_fn"):
        postinst_fn()

    return 0


class PackageProvisionStrategy(TypedDict):
    priority: int  # higher number means earlier
    need_host_blkdevs: list[PartitionKind]
    need_cmd: list[str]
    pretend_fn: Callable[[PartitionMapDecl, PartitionMapDecl], list[str]]
    flash_fn: Callable[[PartitionMapDecl, PartitionMapDecl], int]


def _do_dd(infile: str, outfile: str, blocksize: int = 4096) -> int:
    argv = [
        "sudo",
        "dd",
        f"if={infile}",
        f"of={outfile}",
        f"bs={blocksize}",
    ]

    log.I(
        f"dd-ing [yellow]{infile}[/yellow] to [green]{outfile}[/green] with block size {blocksize}..."
    )
    log.D(f"about to call dd with sudo: argv={argv}")
    retcode = subprocess.call(argv)
    if retcode == 0:
        log.I(f"successfully flashed [green]{outfile}[/green]")
    else:
        log.F(f"failed to flash the [green]{outfile}[/green] disk/partition")
        log.W("the device could be in an inconsistent state now, check now")

    return retcode


def pretend_dd(
    img_paths: PartitionMapDecl, blkdev_paths: PartitionMapDecl
) -> list[str]:
    result: list[str] = []
    for part, img_path in img_paths.items():
        blkdev_path = blkdev_paths[part]
        result.append(
            f"write [yellow]{img_path}[/yellow] contents to [green]{blkdev_path}[/green] with dd"
        )
    return result


def flash_dd(img_paths: PartitionMapDecl, blkdev_paths: PartitionMapDecl) -> int:
    for part, img_path in img_paths.items():
        blkdev_path = blkdev_paths[part]
        ret = _do_dd(img_path, blkdev_path)
        if ret != 0:
            return ret

    return 0


def _do_fastboot(*args: str) -> int:
    argv = ["sudo", "fastboot"]
    argv.extend(args)
    log.D(f"about to call fastboot: argv={argv}")
    return subprocess.call(argv)


def _do_fastboot_flash(part: str, img_path: str) -> int:
    log.I(
        f"flashing [yellow]{img_path}[/yellow] into device partition [green]{part}[/green]"
    )
    ret = _do_fastboot("flash", part, img_path)
    if ret != 0:
        log.F(f"failed to flash [green]{part}[/green] image into device storage")
        log.W("the device could be in an inconsistent state now, check now")
    else:
        log.I(f"[green]{part}[/green] image successfully flashed")

    return ret


def pretend_lpi4a_uboot(img_paths: PartitionMapDecl, _: PartitionMapDecl) -> list[str]:
    p = img_paths["uboot"]
    return [
        f"flash [yellow]{p}[/yellow] into device RAM",
        f"reboot the device",
        f"flash [yellow]{p}[/yellow] into device partition [green]uboot[/green]",
    ]


def flash_lpi4a_uboot(img_paths: PartitionMapDecl, _: PartitionMapDecl) -> int:
    # Perform the equivalent of the following commands from the Sipeed Wiki:
    #
    # sudo ./fastboot flash ram ./images/u-boot-with-spl-lpi4a-16g.bin
    # sudo ./fastboot reboot
    # sleep 1
    # sudo ./fastboot flash uboot ./images/u-boot-with-spl-lpi4a-16g.bin
    #
    # See: https://wiki.sipeed.com/hardware/en/lichee/th1520/lpi4a/4_burn_image.html
    uboot_img_path = img_paths["uboot"]

    log.I("flashing uboot image into device RAM")
    ret = _do_fastboot("flash", "ram", uboot_img_path)
    if ret != 0:
        log.F("failed to flash uboot image into device RAM")
        log.W("the device state should be intact, but please re-check")
        return ret

    log.I("rebooting device into new uboot")
    ret = _do_fastboot("reboot")
    if ret != 0:
        log.F("failed to reboot the device")
        log.W("the device state should be intact, but please re-check")
        return ret

    wait_secs = 1.0
    log.I(f"waiting {wait_secs}s for the device to come back online")
    time.sleep(wait_secs)

    return _do_fastboot_flash("uboot", uboot_img_path)


def pretend_fastboot(img_paths: PartitionMapDecl, _: PartitionMapDecl) -> list[str]:
    return [
        f"flash [yellow]{f}[/yellow] into device partition [green]{p}[/green]"
        for p, f in img_paths.items()
    ]


def flash_fastboot(img_paths: PartitionMapDecl, _: PartitionMapDecl) -> int:
    for partition, img_path in img_paths.items():
        ret = _do_fastboot_flash(partition, img_path)
        if ret != 0:
            return ret

    return 0


STRATEGY_WHOLE_DISK_DD: PackageProvisionStrategy = {
    "priority": 0,
    "need_host_blkdevs": ["disk"],
    "need_cmd": ["sudo", "dd"],
    "pretend_fn": pretend_dd,
    "flash_fn": flash_dd,
}

STRATEGY_BOOT_ROOT_FASTBOOT: PackageProvisionStrategy = {
    "priority": 0,
    "need_host_blkdevs": [],
    "need_cmd": ["sudo", "fastboot"],
    "pretend_fn": pretend_fastboot,
    "flash_fn": flash_fastboot,
}

STRATEGY_UBOOT_FASTBOOT_LPI4A: PackageProvisionStrategy = {
    "priority": 10,
    "need_host_blkdevs": [],
    "need_cmd": ["sudo", "fastboot"],
    "pretend_fn": pretend_lpi4a_uboot,
    "flash_fn": flash_lpi4a_uboot,
}

PKG_PROVISION_STRATEGY: dict[str, PackageProvisionStrategy] = {
    "board-image/buildroot-sdk-milkv-duo": STRATEGY_WHOLE_DISK_DD,
    "board-image/buildroot-sdk-milkv-duo256m": STRATEGY_WHOLE_DISK_DD,
    "board-image/buildroot-sdk-milkv-duo256m-python": STRATEGY_WHOLE_DISK_DD,
    "board-image/buildroot-sdk-milkv-duo-python": STRATEGY_WHOLE_DISK_DD,
    "board-image/oerv-sg2042-milkv-pioneer-base": STRATEGY_WHOLE_DISK_DD,
    "board-image/oerv-sg2042-milkv-pioneer-xfce": STRATEGY_WHOLE_DISK_DD,
    "board-image/oerv-sipeed-lpi4a-headless": STRATEGY_BOOT_ROOT_FASTBOOT,
    "board-image/oerv-sipeed-lpi4a-xfce": STRATEGY_BOOT_ROOT_FASTBOOT,
    "board-image/revyos-sg2042-milkv-pioneer": STRATEGY_WHOLE_DISK_DD,
    "board-image/revyos-sipeed-lpi4a": STRATEGY_BOOT_ROOT_FASTBOOT,
    "board-image/uboot-oerv-sipeed-lpi4a-16g": STRATEGY_UBOOT_FASTBOOT_LPI4A,
    "board-image/uboot-oerv-sipeed-lpi4a-8g": STRATEGY_UBOOT_FASTBOOT_LPI4A,
    "board-image/uboot-revyos-sipeed-lpi4a-16g": STRATEGY_UBOOT_FASTBOOT_LPI4A,
    "board-image/uboot-revyos-sipeed-lpi4a-8g": STRATEGY_UBOOT_FASTBOOT_LPI4A,
}


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
