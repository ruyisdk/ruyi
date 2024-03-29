import re
from _typeshed import Incomplete
from frontmatter import Post
from typing import Any

__all__ = ["BaseHandler", "YAMLHandler", "JSONHandler", "TOMLHandler"]

class BaseHandler:
    FM_BOUNDARY: re.Pattern[str] | None
    START_DELIMITER: str | None
    END_DELIMITER: str | None
    def __init__(
        self,
        fm_boundary: re.Pattern[str] | None = None,
        start_delimiter: str | None = None,
        end_delimiter: str | None = None,
    ) -> None: ...
    def detect(self, text: str) -> bool: ...
    def split(self, text: str) -> tuple[str, str]: ...
    def load(self, fm: str) -> dict[str, Any]: ...
    def export(self, metadata: dict[str, object], **kwargs: object) -> str: ...
    def format(self, post: Post, **kwargs: object) -> str: ...

class YAMLHandler(BaseHandler):
    FM_BOUNDARY: Incomplete
    START_DELIMITER: str
    END_DELIMITER: str
    def load(self, fm: str, **kwargs: object) -> Any: ...
    def export(self, metadata: dict[str, object], **kwargs: object) -> str: ...

class JSONHandler(BaseHandler):
    FM_BOUNDARY: Incomplete
    START_DELIMITER: str
    END_DELIMITER: str
    def split(self, text: str) -> tuple[str, str]: ...
    def load(self, fm: str, **kwargs: object) -> Any: ...
    def export(self, metadata: dict[str, object], **kwargs: object) -> str: ...

class TOMLHandler(BaseHandler):
    FM_BOUNDARY: Incomplete
    START_DELIMITER: str
    END_DELIMITER: str
    def load(self, fm: str, **kwargs: object) -> Any: ...
    def export(self, metadata: dict[str, object], **kwargs: object) -> str: ...
