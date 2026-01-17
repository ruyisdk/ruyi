import base64
import zlib

from .data import RESOURCES, TEMPLATE_NAME_MAP


def _unpack_payload(x: bytes) -> bytes:
    return zlib.decompress(base64.b64decode(x))


def get_resource_blob(name: str) -> bytes | None:
    if t := RESOURCES.get(name):
        return _unpack_payload(t)
    return None


def get_resource_str(name: str) -> str | None:
    if blob := get_resource_blob(name):
        return blob.decode("utf-8")
    return None


def get_template_str(template_name: str) -> str | None:
    if t := TEMPLATE_NAME_MAP.get(template_name):
        return get_resource_str(t)
    return None
