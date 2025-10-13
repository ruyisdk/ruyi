from contextlib import AbstractContextManager
from types import TracebackType
from typing import Iterable

import tomlkit
from tomlkit.container import Container
from tomlkit.items import Array, Comment, InlineTable, Item, Table, Trivia, Whitespace


class NoneValue(Exception):
    """Used to indicate that a None value is to be dumped in TOML. Because TOML
    does not support None natively, this means special handling is needed."""

    def __str__(self) -> str:
        return "NoneValue()"

    def __repr__(self) -> str:
        return "NoneValue()"


def with_indent(item: Item, spaces: int = 2) -> Item:
    item.indent(spaces)
    return item


def inline_table_with_spaces() -> "InlineTableWithSpaces":
    return InlineTableWithSpaces(Container(), Trivia(), new=True)


class InlineTableWithSpaces(InlineTable, AbstractContextManager[InlineTable]):
    def __init__(
        self,
        value: Container,
        trivia: Trivia,
        new: bool = False,
    ) -> None:
        super().__init__(value, trivia, new)

    def __enter__(self) -> InlineTable:
        self.add(tomlkit.ws(" "))
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        self.add(tomlkit.ws(" "))
        return None


def _into_item(x: Item | str) -> Item:
    if isinstance(x, Item):
        return x
    return tomlkit.string(x)


def str_array(
    args: Iterable[Item | str],
    *,
    multiline: bool = False,
    indent: int = 2,
) -> Array:
    items = [_into_item(i).indent(indent) for i in args]
    return Array(items, Trivia(), multiline=multiline)


def sorted_table(x: dict[str, str]) -> Table:
    y = tomlkit.table()
    for k in sorted(x.keys()):
        y.add(k, x[k])
    return y


def extract_header_comments(
    doc: Container,
) -> list[str]:
    comments: list[str] = []

    # ignore leading whitespaces
    is_skipping_leading_ws = True
    for _key, item in doc.body:
        if isinstance(item, Whitespace):
            if is_skipping_leading_ws:
                continue
            # this is part of the header comments
            comments.append(item.as_string())
        elif isinstance(item, Comment):
            is_skipping_leading_ws = False
            comments.append(item.as_string())
        else:
            # we reached the first non-comment item
            break
    return comments


def extract_footer_comments(
    doc: Container,
) -> list[str]:
    comments: list[str] = []

    # ignore trailing whitespaces
    is_skipping_trailing_ws = True
    for _key, item in reversed(doc.body):
        if isinstance(item, Whitespace):
            if is_skipping_trailing_ws:
                continue
            # this is part of the footer comments
            comments.append(item.as_string())
        elif isinstance(item, Comment):
            is_skipping_trailing_ws = False
            comments.append(item.as_string())
        else:
            # we reached the first non-comment item
            break

    # if the footer comment was preceded by a table, then the comment would be
    # nested inside the table and invisible in top-level doc.body, so we would
    # have to check the last item as well
    if not comments:
        last_elem = doc.body[-1][1].value
        if isinstance(last_elem, Container):
            return extract_footer_comments(last_elem)

    return list(reversed(comments))
