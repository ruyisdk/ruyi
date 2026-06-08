import shlex
from typing import Any, Final, Callable, Tuple

from jinja2 import BaseLoader, Environment, TemplateNotFound


class EmbeddedLoader(BaseLoader):
    def __init__(self) -> None:
        pass

    def get_source(
        self,
        environment: Environment,
        template: str,
    ) -> Tuple[str, str | None, Callable[[], bool] | None]:
        from importlib import resources

        path = resources.files("ruyi.resources") / f"{template}.jinja"
        if path.is_file():
            return path.read_text("utf-8"), None, None
        raise TemplateNotFound(template)


_JINJA_ENV: Final = Environment(
    loader=EmbeddedLoader(),
    autoescape=False,  # we're not producing HTML
    auto_reload=False,  # we're serving statically embedded assets
    keep_trailing_newline=True,  # to make shells happy
)
_JINJA_ENV.filters["sh"] = shlex.quote


def render_template_str(template_name: str, data: dict[str, Any]) -> str:
    tmpl = _JINJA_ENV.get_template(template_name)
    return tmpl.render(data)
