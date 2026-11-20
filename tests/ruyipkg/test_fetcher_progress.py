"""Tests for porcelain download progress reporting."""

import os
from typing import Any

import pytest
import requests
from rich import progress as rich_progress

from ruyi.log import ProvidesLoggerAndGlobalMode
from ruyi.ruyipkg.fetcher import PythonRequestsFetcher


class _ChunkedResponse:
    def __init__(
        self,
        status_code: int,
        chunks: list[bytes],
        content_length: int | None = None,
    ) -> None:
        self.status_code = status_code
        self.headers: dict[str, str] = {}
        if content_length is not None:
            self.headers["Content-Length"] = str(content_length)
        self._chunks = chunks
        self.closed = False

    def raise_for_status(self) -> None:
        pass

    def iter_content(self, chunk_size: int) -> Any:
        yield from self._chunks

    def close(self) -> None:
        self.closed = True


class _FakeProgress:
    instances = 0

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        type(self).instances += 1

    def __enter__(self) -> "_FakeProgress":
        return self

    def __exit__(self, *args: Any) -> None:
        return None

    def add_task(self, *args: Any, **kwargs: Any) -> int:
        return 0

    def advance(self, *args: Any, **kwargs: Any) -> None:
        pass


def test_porcelain_mode_skips_human_progress_bar(
    porcelain_logger_and_gm: ProvidesLoggerAndGlobalMode,
    tmp_path: "os.PathLike[str]",
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dest = os.path.join(tmp_path, "distfile")
    response = _ChunkedResponse(200, [b"hello"], content_length=5)
    monkeypatch.setattr(requests, "get", lambda *a, **kw: response)
    monkeypatch.setattr(rich_progress, "Progress", _FakeProgress)
    _FakeProgress.instances = 0

    fetcher = PythonRequestsFetcher(
        porcelain_logger_and_gm,
        ["https://mirror.example/pkg"],
        dest,
    )
    assert fetcher.fetch_one("https://mirror.example/pkg", dest, False)
    assert _FakeProgress.instances == 0


def test_human_mode_uses_progress_bar(
    logger_and_gm: ProvidesLoggerAndGlobalMode,
    tmp_path: "os.PathLike[str]",
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dest = os.path.join(tmp_path, "distfile")
    response = _ChunkedResponse(200, [b"hello"], content_length=5)
    monkeypatch.setattr(requests, "get", lambda *a, **kw: response)
    monkeypatch.setattr(rich_progress, "Progress", _FakeProgress)
    _FakeProgress.instances = 0

    fetcher = PythonRequestsFetcher(
        logger_and_gm,
        ["https://mirror.example/pkg"],
        dest,
    )
    assert fetcher.fetch_one("https://mirror.example/pkg", dest, False)
    assert _FakeProgress.instances == 1
