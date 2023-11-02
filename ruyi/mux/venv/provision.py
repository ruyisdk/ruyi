import base64
from os import PathLike
import pathlib
import shlex
from typing import Any, Callable, Tuple
import zlib

from jinja2 import BaseLoader, Environment, TemplateNotFound

from .data import TEMPLATES


def unpack_payload(x: bytes) -> str:
    return zlib.decompress(base64.b64decode(x)).decode("utf-8")


class EmbeddedLoader(BaseLoader):
    def __init__(self, payloads: dict[str, bytes]) -> None:
        self._payloads = payloads

    def get_source(
        self, _: Environment, template: str
    ) -> Tuple[str, str | None, Callable[[], bool] | None]:
        payload = self._payloads.get(template)
        if payload is None:
            raise TemplateNotFound(template)
        return unpack_payload(payload), None, None


JINJA_ENV = Environment(
    loader=EmbeddedLoader(TEMPLATES),
    autoescape=False,  # we're not producing HTML
    auto_reload=False,  # we're serving statically embedded assets
    keep_trailing_newline=True,  # to make shells happy
)
JINJA_ENV.filters["sh"] = shlex.quote


def render_and_write(dest: PathLike, template_name: str, data: dict[str, Any]) -> None:
    tmpl = JINJA_ENV.get_template(template_name)
    content = tmpl.render(data).encode("utf-8")
    with open(dest, "wb") as fp:
        fp.write(content)


class VenvMaker:
    def __init__(
        self,
        dest: PathLike,
        override_name: str | None = None,
    ) -> None:
        self.dest = dest
        self.override_name = override_name

    def provision(self) -> None:
        venv_root = pathlib.Path(self.dest)
        venv_root.mkdir()

        bindir = venv_root / "bin"
        bindir.mkdir()

        template_data = {
            "RUYI_VENV": str(self.dest),
            "RUYI_VENV_NAME": self.override_name,
        }

        render_and_write(bindir / "ruyi-activate", "ruyi-activate.bash", template_data)
