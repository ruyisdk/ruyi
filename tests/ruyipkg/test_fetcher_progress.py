"""Tests for porcelain download progress reporting."""

import json
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


def _download_events(stderr: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line in stderr.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if str(obj.get("ty", "")).startswith("download"):
            events.append(obj)
    return events


def test_request_event_announces_each_attempt(
    porcelain_logger_and_gm: ProvidesLoggerAndGlobalMode,
    tmp_path: "os.PathLike[str]",
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
) -> None:
    dest = os.path.join(tmp_path, "distfile")
    url = "https://mirror.example/pkg"
    response = _ChunkedResponse(200, [b"hello"], content_length=5)
    monkeypatch.setattr(requests, "get", lambda *a, **kw: response)

    fetcher = PythonRequestsFetcher(porcelain_logger_and_gm, [url], dest)
    assert fetcher.fetch_one(url, dest, False)

    events = _download_events(capfd.readouterr().err)
    request_events = [e for e in events if e["ty"] == "downloadrequest-v1"]

    assert len(request_events) == 1
    assert request_events[0]["url"] == url
    assert request_events[0]["dest_path"] == dest
    assert request_events[0]["req_id"]


def test_progress_reports_each_percent(
    porcelain_logger_and_gm: ProvidesLoggerAndGlobalMode,
    tmp_path: "os.PathLike[str]",
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
) -> None:
    dest = os.path.join(tmp_path, "distfile")
    chunks = [bytes([i]) for i in range(100)]
    response = _ChunkedResponse(200, chunks, content_length=100)
    monkeypatch.setattr(requests, "get", lambda *a, **kw: response)

    fetcher = PythonRequestsFetcher(
        porcelain_logger_and_gm,
        ["https://mirror.example/pkg"],
        dest,
    )
    assert fetcher.fetch_one("https://mirror.example/pkg", dest, False)

    events = _download_events(capfd.readouterr().err)
    request_events = [e for e in events if e["ty"] == "downloadrequest-v1"]
    progress_events = [e for e in events if e["ty"] == "downloadprogress-v1"]

    assert [e["progress_bytes"] for e in progress_events] == list(range(101))
    assert [e["done"] for e in progress_events] == [False] * 100 + [True]
    assert all(e["total_bytes"] == 100 for e in progress_events)
    assert all(e["error"] is None for e in progress_events)
    assert all(e["req_id"] == request_events[0]["req_id"] for e in progress_events)


def test_progress_uses_one_mib_steps_when_total_is_unknown(
    porcelain_logger_and_gm: ProvidesLoggerAndGlobalMode,
    tmp_path: "os.PathLike[str]",
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
) -> None:
    dest = os.path.join(tmp_path, "distfile")
    mib = 1024 * 1024
    chunks = [b"a" * mib, b"b" * mib, b"c" * mib]
    response = _ChunkedResponse(200, chunks, content_length=None)
    monkeypatch.setattr(requests, "get", lambda *a, **kw: response)

    fetcher = PythonRequestsFetcher(
        porcelain_logger_and_gm,
        ["https://mirror.example/pkg"],
        dest,
    )
    assert fetcher.fetch_one("https://mirror.example/pkg", dest, False)

    events = _download_events(capfd.readouterr().err)
    progress_events = [e for e in events if e["ty"] == "downloadprogress-v1"]

    assert [e["progress_bytes"] for e in progress_events] == [
        0,
        mib,
        2 * mib,
        3 * mib,
    ]
    assert [e["done"] for e in progress_events] == [False, False, False, True]
    assert all(e["total_bytes"] is None for e in progress_events)


def test_progress_emits_once_per_chunk_that_crosses_percent(
    porcelain_logger_and_gm: ProvidesLoggerAndGlobalMode,
    tmp_path: "os.PathLike[str]",
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
) -> None:
    dest = os.path.join(tmp_path, "distfile")
    response = _ChunkedResponse(200, [b"x" * 50, b"y" * 50], content_length=100)
    monkeypatch.setattr(requests, "get", lambda *a, **kw: response)

    fetcher = PythonRequestsFetcher(
        porcelain_logger_and_gm,
        ["https://mirror.example/pkg"],
        dest,
    )
    assert fetcher.fetch_one("https://mirror.example/pkg", dest, False)

    events = _download_events(capfd.readouterr().err)
    progress_events = [e for e in events if e["ty"] == "downloadprogress-v1"]

    assert [e["progress_bytes"] for e in progress_events] == [0, 50, 100]
    assert [e["done"] for e in progress_events] == [False, False, True]


def test_progress_starts_from_existing_partial_when_resuming(
    porcelain_logger_and_gm: ProvidesLoggerAndGlobalMode,
    tmp_path: "os.PathLike[str]",
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
) -> None:
    dest = os.path.join(tmp_path, "distfile")
    with open(dest, "wb") as f:
        f.write(b"A" * 40)

    chunks = [b"B"] * 60
    response = _ChunkedResponse(200, chunks, content_length=60)
    seen: dict[str, str] = {}

    def fake_get(url: str, **kwargs: Any) -> Any:
        seen.update(kwargs["headers"])
        return response

    monkeypatch.setattr(requests, "get", fake_get)

    fetcher = PythonRequestsFetcher(
        porcelain_logger_and_gm,
        ["https://mirror.example/pkg"],
        dest,
    )
    assert fetcher.fetch_one("https://mirror.example/pkg", dest, True)

    assert seen["Range"] == "bytes=40-"
    events = _download_events(capfd.readouterr().err)
    progress_events = [e for e in events if e["ty"] == "downloadprogress-v1"]

    assert [e["progress_bytes"] for e in progress_events] == list(range(40, 101))
    assert all(e["total_bytes"] == 100 for e in progress_events)
    assert progress_events[-1]["done"] is True


def test_no_progress_events_in_human_mode(
    logger_and_gm: ProvidesLoggerAndGlobalMode,
    tmp_path: "os.PathLike[str]",
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
) -> None:
    dest = os.path.join(tmp_path, "distfile")
    response = _ChunkedResponse(200, [b"x" * 10], content_length=10)
    monkeypatch.setattr(requests, "get", lambda *a, **kw: response)
    monkeypatch.setattr(rich_progress, "Progress", _FakeProgress)
    _FakeProgress.instances = 0

    fetcher = PythonRequestsFetcher(
        logger_and_gm,
        ["https://mirror.example/pkg"],
        dest,
    )
    assert fetcher.fetch_one("https://mirror.example/pkg", dest, False)

    assert _download_events(capfd.readouterr().err) == []


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


def test_request_ids_are_distinct_and_events_are_ordered_across_attempts(
    porcelain_logger_and_gm: ProvidesLoggerAndGlobalMode,
    tmp_path: "os.PathLike[str]",
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
) -> None:
    dest = os.path.join(tmp_path, "distfile")
    url = "https://mirror.example/pkg"
    responses = [
        _ChunkedResponse(200, [b"first"], content_length=5),
        _ChunkedResponse(200, [b"second"], content_length=6),
    ]

    def fake_get(*args: Any, **kwargs: Any) -> _ChunkedResponse:
        return responses.pop(0)

    monkeypatch.setattr(requests, "get", fake_get)
    fetcher = PythonRequestsFetcher(porcelain_logger_and_gm, [url], dest)

    assert fetcher.fetch_one(url, dest, False)
    assert fetcher.fetch_one(url, dest, False)

    events = _download_events(capfd.readouterr().err)
    request_events = [e for e in events if e["ty"] == "downloadrequest-v1"]
    assert len(request_events) == 2

    req_ids = [e["req_id"] for e in request_events]
    assert len(set(req_ids)) == 2

    # progress events follow the request event that introduced their req_id
    current_req_id: str | None = None
    seen_progress: set[str] = set()
    for event in events:
        if event["ty"] == "downloadrequest-v1":
            current_req_id = event["req_id"]
            continue
        assert event["ty"] == "downloadprogress-v1"
        assert event["req_id"] == current_req_id
        seen_progress.add(event["req_id"])

    assert seen_progress == set(req_ids)
