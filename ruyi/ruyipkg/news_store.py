import functools
import re
from typing import Any, Final, TypedDict

from ..config.news import NewsReadStatusStore
from ..utils import frontmatter
from ..utils.porcelain import PorcelainEntity, PorcelainEntityType
from ..utils.l10n import match_lang_code

NEWS_FILENAME_RE: Final = re.compile(r"^(\d+-\d{2}-\d{2}-.*?)(\.[0-9A-Za-z_-]+)?\.md$")


@functools.total_ordering
class NewsItemNameMetadata:
    def __init__(self, id: str, lang: str) -> None:
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
        lang = "zh_CN"  # TODO: kill after l10n work is complete
    else:
        lang = lang[1:]  # strip the dot prefix

    return NewsItemNameMetadata(id, lang)


class NewsItemStore:
    def __init__(self, rs_store: NewsReadStatusStore) -> None:
        self._buf_news_by_ids: dict[str, NewsItem] = {}
        self._newsitems: list[NewsItem]
        self._rs_store = rs_store

    def add(self, filename: str, contents: str) -> None:
        md = parse_news_filename(filename)
        if md is None:
            return None

        post = frontmatter.loads(contents)

        if ni := self._buf_news_by_ids.get(md.id):
            ni.add_lang(md, post)
        else:
            ni = NewsItem(md.id)
            ni.add_lang(md, post)
            self._buf_news_by_ids[md.id] = ni

    def finalize(self) -> None:
        self._newsitems = list(self._buf_news_by_ids.values())
        # sort in intended display order
        self._newsitems.sort()

        # mark the news item instances with ordinals
        for i, ni in enumerate(self._newsitems):
            ni.ordinal = i + 1

        # also read statuses
        for ni in self._newsitems:
            ni.is_read = ni.id in self._rs_store

    def list(self, only_unread: bool) -> list["NewsItem"]:
        if not only_unread:
            return self._newsitems
        return [x for x in self._newsitems if not x.is_read]

    def mark_as_read(self, *ids: str) -> None:
        if not ids:
            return
        for id in ids:
            self._rs_store.add(id)
        self._rs_store.save()


@functools.total_ordering
class NewsItem:
    def __init__(self, id: str) -> None:
        self._id = id
        self._content_by_lang: dict[str, NewsItemContent] = {}

        # these fields are updated later in store initialization code
        self.ordinal = 0
        self.is_read = False

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, NewsItem):
            return NotImplemented
        return self._id == other._id and self.ordinal == other.ordinal

    def __lt__(self, other: Any) -> bool:
        if not isinstance(other, NewsItem):
            return NotImplemented
        return self._id < other._id or self.ordinal < other.ordinal

    @property
    def id(self) -> str:
        return self._id

    def __contains__(self, lang: str) -> bool:
        return lang in self._content_by_lang

    def __getitem__(self, lang: str) -> "NewsItemContent":
        return self._content_by_lang[lang]

    def add_lang(self, md: NewsItemNameMetadata, post: frontmatter.Post) -> None:
        self._content_by_lang[md.lang] = NewsItemContent(md, post)

    def __delitem__(self, lang: str) -> None:
        del self._content_by_lang[lang]

    def get_content_for_lang(self, lang: str) -> "NewsItemContent":
        resolved_lang_code = match_lang_code(lang, self._content_by_lang.keys())
        return self[resolved_lang_code]

    def to_porcelain(self) -> "PorcelainNewsItemV1":
        return {
            "ty": PorcelainEntityType.NewsItemV1,
            "id": self.id,
            "ord": self.ordinal,
            "is_read": self.is_read,
            "langs": [x.to_porcelain() for x in self._content_by_lang.values()],
        }


class NewsItemContent:
    def __init__(
        self,
        md: NewsItemNameMetadata,
        post: frontmatter.Post,
    ) -> None:
        self._md = md
        self._post = post

    @property
    def lang(self) -> str:
        return self._md.lang

    @property
    def display_title(self) -> str:
        metadata_title = self._post.get("title")
        return metadata_title if isinstance(metadata_title, str) else self._md.id

    @property
    def content(self) -> str:
        return self._post.content

    def to_porcelain(self) -> "PorcelainNewsItemContentV1":
        return {
            "lang": self.lang,
            "display_title": self.display_title,
            "content": self.content,
        }


class PorcelainNewsItemContentV1(TypedDict):
    lang: str
    display_title: str
    content: str


class PorcelainNewsItemV1(PorcelainEntity):
    id: str
    ord: int
    is_read: bool
    langs: list[PorcelainNewsItemContentV1]
