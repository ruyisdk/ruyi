#!/usr/bin/env python3
# Regenerates data.py from fresh contents.

import base64
import pathlib
from typing import Any
import zlib


def make_payload_from_file(path: pathlib.Path) -> str:
    with open(path, "rb") as fp:
        content = fp.read()

    return base64.b64encode(zlib.compress(content, 9)).decode("ascii")


def main() -> None:
    self_path = pathlib.Path(__file__).parent.resolve()
    bundled_resource_root = self_path / ".." / ".." / "resources" / "bundled"

    resources: dict[str, str] = {}
    template_names: dict[str, str] = {}
    for f in bundled_resource_root.iterdir():
        if not f.is_file():
            continue

        resources[f.name] = make_payload_from_file(f)

        if f.suffix.lower() == ".jinja":
            # strip the .jinja suffix for the template name
            template_names[f.stem] = f.name

    with open(self_path / "data.py", "w", encoding="utf-8") as fp:

        def p(*args: Any) -> None:
            return print(*args, file=fp)

        p("# NOTE: This file is auto-generated. DO NOT EDIT!")
        p("# Update by running the __main__.py alongside this file\n")

        p("from typing import Final\n\n")

        p("RESOURCES: Final = {")
        for filename, payload in sorted(resources.items()):
            p(f'    "{filename}": b"{payload}",  # fmt: skip')
        p("}\n")

        p("TEMPLATES: Final = {")
        for stem, full_filename in sorted(template_names.items()):
            p(f'    "{stem}": RESOURCES["{full_filename}"],')
        p("}")


if __name__ == "__main__":
    main()
