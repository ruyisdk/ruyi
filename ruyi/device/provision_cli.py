import argparse
from typing import TypedDict

from .. import log
from ..cli import user_input


class ImageComboDecl(TypedDict):
    id: str
    display_name: str
    packages: list[str]


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
        "id": "oerv-sipeed-lpi4a-8g-headless",
        "display_name": "openEuler RISC-V (headless) for Sipeed LicheePi 4A (8G RAM)",
        "packages": [
            "board-image/oerv-sipeed-lpi4a-headless",
            "uboot-oerv-sipeed-lpi4a-8g",
        ],
    },
    {
        "id": "oerv-sipeed-lpi4a-8g-xfce",
        "display_name": "openEuler RISC-V (XFCE) for Sipeed LicheePi 4A (8G RAM)",
        "packages": [
            "board-image/oerv-sipeed-lpi4a-xfce",
            "uboot-oerv-sipeed-lpi4a-8g",
        ],
    },
    {
        "id": "oerv-sipeed-lpi4a-16g-headless",
        "display_name": "openEuler RISC-V (headless) for Sipeed LicheePi 4A (16G RAM)",
        "packages": [
            "board-image/oerv-sipeed-lpi4a-headless",
            "uboot-oerv-sipeed-lpi4a-16g",
        ],
    },
    {
        "id": "oerv-sipeed-lpi4a-16g-xfce",
        "display_name": "openEuler RISC-V (XFCE) for Sipeed LicheePi 4A (16G RAM)",
        "packages": [
            "board-image/oerv-sipeed-lpi4a-xfce",
            "uboot-oerv-sipeed-lpi4a-16g",
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
            "board-image/uboot-sipeed-lpi4a-8g",
        ],
    },
    {
        "id": "revyos-sipeed-lpi4a-16g",
        "display_name": "RevyOS for Sipeed LicheePi 4A (16G RAM)",
        "packages": [
            "board-image/revyos-sipeed-lpi4a",
            "board-image/uboot-sipeed-lpi4a-16g",
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
                "oerv-milkv-pioneer-base",
                "oerv-milkv-pioneer-xfce",
                "revyos-milkv-pioneer",
            ],
        },
        {
            "id": "v1.2",
            "display_name": "Milk-V Pioneer Box (v1.2)",
            "supported_combos": [
                # "fedora-milkv-pioneer-v1.2"  # cannot download from Google Drive
                "oerv-milkv-pioneer-base",  # unconfirmed by PM
                "oerv-milkv-pioneer-xfce",  # unconfirmed by PM
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
required to flash images, you should arrange to allow your user account write
access to the block device files. This likely means you should ensure your
user is part of the [yellow]disk[/yellow] group; for example, you can
[yellow]sudo gpasswd -a <your user> disk[/yellow] then logout and re-login, to achieve this.
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

    return do_provision_combo_interactive(dev, variant, combo)


def do_provision_combo_interactive(
    dev_decl: DeviceDecl,
    variant_decl: DeviceVariantDecl,
    combo: ImageComboDecl,
) -> int:
    log.D(f"provisioning device variant '{dev_decl['id']}@{variant_decl['id']}'")
    log.D(f"chosen combo: packages {combo['packages']}")

    # TODO: download packages

    # TODO: prompt target block device(s)

    # TODO: final confirmation

    # TODO: flash with dd

    # TODO: parting words

    return 0
