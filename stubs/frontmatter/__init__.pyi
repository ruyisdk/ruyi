import io
from .default_handlers import BaseHandler
from _typeshed import Incomplete
from typing import Iterable

__all__ = ["parse", "load", "loads", "dump", "dumps"]

def parse(
    text: str,
    encoding: str = "utf-8",
    handler: BaseHandler | None = None,
    **defaults: object,
) -> tuple[dict[str, object], str]: ...
def load(
    fd: str | io.IOBase,
    encoding: str = "utf-8",
    handler: BaseHandler | None = None,
    **defaults: object,
) -> Post: ...
def loads(
    text: str,
    encoding: str = "utf-8",
    handler: BaseHandler | None = None,
    **defaults: object,
) -> Post: ...
def dump(
    post: Post,
    fd: str | io.IOBase,
    encoding: str = "utf-8",
    handler: BaseHandler | None = None,
    **kwargs: object,
) -> None: ...
def dumps(post: Post, handler: BaseHandler | None = None, **kwargs: object) -> str: ...

class Post:
    content: str
    metadata: dict[str, object]
    handler: BaseHandler | None
    def __init__(
        self, content: str, handler: BaseHandler | None = None, **metadata: object
    ) -> None: ...
    def __getitem__(self, name: str) -> object: ...
    def __contains__(self, item: object) -> bool: ...
    def __setitem__(self, name: str, value: object) -> None: ...
    def __delitem__(self, name: str) -> None: ...
    def __bytes__(self) -> bytes: ...
    def get(self, key: str, default: object = None) -> object: ...
    def keys(self) -> Iterable[str]: ...
    def values(self) -> Iterable[object]: ...
    def to_dict(self) -> dict[str, object]: ...
