import base64
import shlex
from typing import Any, Final, Callable, Tuple
import zlib

from jinja2 import BaseLoader, Environment, TemplateNotFound

from .data import TEMPLATES


def _unpack_payload(x: bytes) -> str:
    return zlib.decompress(base64.b64decode(x)).decode("utf-8")


class EmbeddedLoader(BaseLoader):
    def __init__(self, payloads: dict[str, bytes]) -> None:
        self._payloads = payloads

    def get_source(
        self,
        environment: Environment,
        template: str,
    ) -> Tuple[str, str | None, Callable[[], bool] | None]:
        payload = self._payloads.get(template)
        if payload is None:
            raise TemplateNotFound(template)
        return _unpack_payload(payload), None, None


_JINJA_ENV: Final = Environment(
    loader=EmbeddedLoader(TEMPLATES),
    autoescape=False,  # we're not producing HTML
    auto_reload=False,  # we're serving statically embedded assets
    keep_trailing_newline=True,  # to make shells happy
)
_JINJA_ENV.filters["sh"] = shlex.quote


def render_template_str(template_name: str, data: dict[str, Any]) -> str:
    tmpl = _JINJA_ENV.get_template(template_name)
    return tmpl.render(data)
