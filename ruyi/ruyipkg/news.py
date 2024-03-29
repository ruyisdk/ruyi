import functools
import re
from typing import Any, Self

import frontmatter

NEWS_FILENAME_RE = re.compile(r"^(\d+-\d{2}-\d{2}-.*)(\.[0-9A-Za-z_-]+)?\.md$")


@functools.total_ordering
class NewsItemNameMetadata:
    def __init__(self, id: str, lang: str | None = None) -> None:
        self.id = id
        self.lang = lang

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, NewsItemNameMetadata):
            return NotImplemented
        return self.id == other.id

    def __lt__(self, other: Any) -> bool:
        if not isinstance(other, NewsItemNameMetadata):
            return NotImplemented

        # order by id in lexical order
        return self.id < other.id


def parse_news_filename(filename: str) -> NewsItemNameMetadata | None:
    m = NEWS_FILENAME_RE.match(filename)
    if m is None:
        return None

    id = m.group(1)
    lang = m.group(2)
    if not lang:
        lang = None

    return NewsItemNameMetadata(id, lang)


@functools.total_ordering
class NewsItem:
    def __init__(
        self,
        md: NewsItemNameMetadata,
        post: frontmatter.Post,
    ) -> None:
        self._md = md
        self._post = post
        self.ordinal = 0  # may be updated later in repo code

    @classmethod
    def new(cls, filename: str, contents: str) -> Self | None:
        md = parse_news_filename(filename)
        if md is None:
            return None

        post = frontmatter.loads(contents)
        return cls(md, post)

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, NewsItem):
            return NotImplemented
        return self._md == other._md

    def __lt__(self, other: Any) -> bool:
        if not isinstance(other, NewsItem):
            return NotImplemented
        return self._md < other._md

    @property
    def id(self) -> str:
        return self._md.id

    @property
    def lang(self) -> str | None:
        return self._md.lang

    @property
    def display_title(self) -> str:
        metadata_title = self._post.get("title")
        return metadata_title if isinstance(metadata_title, str) else self.id

    @property
    def content(self) -> str:
        return self._post.content
