from contextlib import AbstractContextManager
import enum
import json
import sys
from types import TracebackType
from typing import BinaryIO, TypedDict, TYPE_CHECKING

if TYPE_CHECKING:
    from typing_extensions import Self

if sys.version_info >= (3, 11):

    class PorcelainEntityType(enum.StrEnum):
        LogV1 = "log-v1"
        NewsItemV1 = "newsitem-v1"
        PkgListOutputV1 = "pkglistoutput-v1"
        EntityListOutputV1 = "entitylistoutput-v1"

else:

    class PorcelainEntityType(str, enum.Enum):
        LogV1 = "log-v1"
        NewsItemV1 = "newsitem-v1"
        PkgListOutputV1 = "pkglistoutput-v1"
        EntityListOutputV1 = "entitylistoutput-v1"


class PorcelainEntity(TypedDict):
    ty: PorcelainEntityType


class PorcelainOutput(AbstractContextManager["PorcelainOutput"]):
    def __init__(self, out: BinaryIO | None = None) -> None:
        self.out = sys.stdout.buffer if out is None else out

    def __enter__(self) -> "Self":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        self.out.flush()
        return None

    def emit(self, obj: PorcelainEntity) -> None:
        s = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
        self.out.write(s.encode("utf-8"))
        self.out.write(b"\n")
