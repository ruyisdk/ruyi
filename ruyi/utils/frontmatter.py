# Minimal frontmatter support for Markdown, because [python-frontmatter] is
# not packaged in major Linux distributions, complicating packaging work.
#
# Only the YAML frontmatter is supported here, unlike python-frontmatter
# which supports additionally JSON and TOML frontmatter formats.
#
# [python-frontmatter]: https://github.com/eyeseast/python-frontmatter

import re
from typing import Final
import yaml


FRONTMATTER_BOUNDARY_RE: Final = re.compile(r"(?m)^-{3,}\s*$")


class Post:
    def __init__(self, metadata: dict[str, object] | None, content: str) -> None:
        self._md = metadata
        self.content = content

    def get(self, key: str) -> object | None:
        return None if self._md is None else self._md.get(key)


def loads(s: str) -> Post:
    m = FRONTMATTER_BOUNDARY_RE.match(s)
    if m is None:
        return Post(None, s)

    x = FRONTMATTER_BOUNDARY_RE.split(s, 2)
    if len(x) != 3:
        return Post(None, s)

    fm, content = x[1], x[2]

    metadata = yaml.safe_load(fm)
    return Post(metadata, content)
