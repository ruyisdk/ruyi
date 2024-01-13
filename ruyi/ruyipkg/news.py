import functools
import re
from typing import Self

import frontmatter

NEWS_FILENAME_RE = re.compile(r"^(\d+)-(\d{2})-(\d{2})-(.*)\.md$")


@functools.total_ordering
class NewsItemNameMetadata:
    def __init__(self, ymd: int, id: str) -> None:
        self.ymd = ymd  # e.g. 20240102
        self.id = id

    def __eq__(self, other):
        if not isinstance(other, NewsItemNameMetadata):
            return NotImplemented
        return self.ymd == other.ymd and self.id == other.id

    def __lt__(self, other):
        if not isinstance(other, NewsItemNameMetadata):
            return NotImplemented

        # order by ymd first, in ascending order so ordinals stay stable
        if self.ymd != other.ymd:
            return self.ymd < other.ymd

        # then order by id in lexical order
        return self.id < other.id


def parse_news_filename(filename: str) -> NewsItemNameMetadata | None:
    m = NEWS_FILENAME_RE.match(filename)
    if m is None:
        return None

    year = int(m.group(1))
    month = int(m.group(2))
    day = int(m.group(3))
    ymd = year * 10000 + month * 100 + day
    id = m.group(4)
    return NewsItemNameMetadata(ymd, id)


@functools.total_ordering
class NewsItem:
    def __init__(
        self,
        md: NewsItemNameMetadata,
        post: frontmatter.Post,
    ) -> None:
        self._md = md
        self._post = post

    @classmethod
    def new(cls, filename: str, contents: str) -> Self | None:
        md = parse_news_filename(filename)
        if md is None:
            return None

        post = frontmatter.loads(contents)
        return cls(md, post)

    def __eq__(self, other):
        if not isinstance(other, NewsItem):
            return NotImplemented
        return self._md == other._md

    def __lt__(self, other):
        if not isinstance(other, NewsItem):
            return NotImplemented
        return self._md < other._md

    @property
    def id(self) -> str:
        return self._md.id

    @property
    def display_title(self) -> str:
        return self._post.get("title") or self.id

    @property
    def content(self) -> str:
        return self._post.content
