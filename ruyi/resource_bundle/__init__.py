import base64
import zlib

from .data import TEMPLATES


def _unpack_payload(x: bytes) -> str:
    return zlib.decompress(base64.b64decode(x)).decode("utf-8")


def get_resource_str(template_name: str) -> str | None:
    if t := TEMPLATES.get(template_name):
        return _unpack_payload(t)
    return None
