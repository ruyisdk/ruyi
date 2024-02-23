from typing import Literal, NotRequired, TypeAlias, TypedDict


class ImageComboDecl(TypedDict):
    id: str
    display_name: str
    packages: list[str]
    postinst_msgid: NotRequired[str]


class DeviceVariantDecl(TypedDict):
    id: str
    display_name: str
    supported_combos: list[str]


class DeviceDecl(TypedDict):
    id: str
    display_name: str
    variants: list[DeviceVariantDecl]


ProvisionerConfigVersion: TypeAlias = Literal["v1"]


class ProvisionerConfig(TypedDict):
    ruyi_provisioner_config: ProvisionerConfigVersion
    devices: list[DeviceDecl]
    image_combos: list[ImageComboDecl]
    postinst_messages: NotRequired[dict[str, str]]
