from contextlib import AbstractContextManager
import enum
import io
import json
import sys
from types import TracebackType
from typing import Protocol, TypedDict, TYPE_CHECKING

if TYPE_CHECKING:
    from typing_extensions import Self


class PorcelainEntityType(enum.StrEnum):
    LogV1 = "log-v1"
    NewsItemV1 = "newsitem-v1"
    PkgListOutputV1 = "pkglistoutput-v1"
    EntityListOutputV1 = "entitylistoutput-v1"
    RepoEntryV1 = "repoentry-v1"
    CheckDiagnosticV1 = "checkdiagnostic-v1"


class PorcelainEntity(TypedDict):
    ty: PorcelainEntityType


class PorcelainBinarySink(Protocol):
    def flush(self) -> None: ...
    def write(self, b: bytes, /) -> int: ...


class PorcelainTextSink(Protocol):
    def flush(self) -> None: ...
    def write(self, s: str, /) -> int: ...


class PorcelainOutput(AbstractContextManager["PorcelainOutput"]):
    def __init__(
        self,
        *,
        binary_out: PorcelainBinarySink | None = None,
        text_out: PorcelainTextSink | None = None,
    ) -> None:
        self._txt_out: PorcelainTextSink | None
        self._bin_out: PorcelainBinarySink | None

        if binary_out is None and text_out is None:
            if isinstance(sys.stdout, io.TextIOWrapper):
                self._bin_out = sys.stdout.buffer
                self._txt_out = None
            else:
                self._bin_out = None
                self._txt_out = sys.stdout
            return

        if binary_out is not None and text_out is not None:
            raise ValueError("cannot specify both binary_out and text_out")

        self._txt_out = text_out
        self._bin_out = binary_out

    def __enter__(self) -> "Self":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        if self._txt_out is not None:
            self._txt_out.flush()
        if self._bin_out is not None:
            self._bin_out.flush()
        return None

    def emit(self, obj: PorcelainEntity) -> None:
        s = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
        if self._txt_out is not None:
            self._txt_out.write(s)
            self._txt_out.write("\n")
            return
        assert self._bin_out is not None
        self._bin_out.write(s.encode("utf-8"))
        self._bin_out.write(b"\n")
