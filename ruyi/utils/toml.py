from contextlib import AbstractContextManager
from types import TracebackType
from typing import Iterable

import tomlkit
from tomlkit.container import Container
from tomlkit.items import Array, InlineTable, Item, Table, Trivia


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
