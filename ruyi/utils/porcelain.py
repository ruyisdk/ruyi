from contextlib import AbstractContextManager
from enum import StrEnum
import json
import sys
from types import TracebackType
from typing import BinaryIO, TypedDict

from typing_extensions import Self


class PorcelainEntityType(StrEnum):
    LogV1 = "log-v1"
    NewsItemV1 = "newsitem-v1"
    PkgListOutputV1 = "pkglistoutput-v1"


class PorcelainEntity(TypedDict):
    ty: PorcelainEntityType


class PorcelainOutput(AbstractContextManager["PorcelainOutput"]):
    def __init__(self, out: BinaryIO | None = None) -> None:
        if out is None:
            out = sys.stdout.buffer
        self.out = out

    def __enter__(self) -> Self:
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
