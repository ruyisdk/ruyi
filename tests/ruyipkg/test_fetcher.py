"""Regression tests for the distfile mirror fallback logic.

See https://github.com/ruyisdk/ruyi/issues/498: a mirror serving a
complete-but-wrong file (e.g. an HTTP 200 error page) used to abort the whole
fetch instead of falling through to the next mirror in the list.
"""

import os
from typing import Callable

import pytest

from ruyi.log import RuyiLogger
from ruyi.ruyipkg.fetcher import BaseFetcher


class RecordingFetcher(BaseFetcher):
    """A fetcher that "downloads" canned per-URL content and records calls."""

    def __init__(
        self,
        logger: RuyiLogger,
        urls: list[str],
        dest: str,
        url_content: dict[str, bytes],
    ) -> None:
        super().__init__(logger, urls, dest)
        self._url_content = url_content
        self.calls: list[tuple[str, bool]] = []

    @classmethod
    def is_available(cls, logger: RuyiLogger) -> bool:
        return True

    def fetch_one(self, url: str, dest: str, resume: bool) -> bool:
        self.calls.append((url, resume))
        content = self._url_content.get(url)
        if content is None:
            # simulate a download-command failure (e.g. connection refused)
            return False
        # simulate a successful download regardless of content correctness,
        # mirroring how curl/wget exit 0 for an HTTP 200 error page
        with open(dest, "wb") as f:
            f.write(content)
        return True


def _accept_only(good: bytes, dest: str) -> Callable[[], bool]:
    def validator() -> bool:
        with open(dest, "rb") as f:
            if f.read() == good:
                return True
        # a real validator discards the bad file
        os.remove(dest)
        return False

    return validator


def test_fetch_falls_through_to_next_url_on_validation_failure(
    ruyi_logger: RuyiLogger,
    tmp_path: "os.PathLike[str]",
) -> None:
    dest = os.path.join(tmp_path, "distfile")
    good = b"correct contents"
    urls = ["https://mirror.example/bad", "https://upstream.example/good"]
    fetcher = RecordingFetcher(
        ruyi_logger,
        urls,
        dest,
        {
            urls[0]: b"<html>200 but wrong</html>",
            urls[1]: good,
        },
    )

    fetcher.fetch(post_fetch_validator=_accept_only(good, dest))

    # both mirrors were tried, and the good contents landed on disk
    assert [c[0] for c in fetcher.calls] == urls
    with open(dest, "rb") as f:
        assert f.read() == good


def test_fetch_stops_at_first_valid_url(
    ruyi_logger: RuyiLogger,
    tmp_path: "os.PathLike[str]",
) -> None:
    dest = os.path.join(tmp_path, "distfile")
    good = b"correct contents"
    urls = ["https://mirror.example/good", "https://upstream.example/good"]
    fetcher = RecordingFetcher(
        ruyi_logger,
        urls,
        dest,
        {urls[0]: good, urls[1]: good},
    )

    fetcher.fetch(post_fetch_validator=_accept_only(good, dest))

    # the second mirror must not be contacted once the first one validates
    assert [c[0] for c in fetcher.calls] == [urls[0]]


def test_fetch_raises_when_all_urls_fail_validation(
    ruyi_logger: RuyiLogger,
    tmp_path: "os.PathLike[str]",
) -> None:
    dest = os.path.join(tmp_path, "distfile")
    good = b"correct contents"
    urls = ["https://mirror.example/bad1", "https://mirror.example/bad2"]
    fetcher = RecordingFetcher(
        ruyi_logger,
        urls,
        dest,
        {urls[0]: b"wrong 1", urls[1]: b"wrong 2"},
    )

    with pytest.raises(RuntimeError, match="all source URLs have failed"):
        fetcher.fetch(post_fetch_validator=_accept_only(good, dest))

    assert [c[0] for c in fetcher.calls] == urls


def test_fetch_disables_resume_after_validation_failure(
    ruyi_logger: RuyiLogger,
    tmp_path: "os.PathLike[str]",
) -> None:
    # A failing validator removes the partial file, so resuming from the next
    # mirror would target a file that no longer exists; resume must be dropped.
    dest = os.path.join(tmp_path, "distfile")
    good = b"correct contents"
    urls = ["https://mirror.example/bad", "https://upstream.example/good"]
    fetcher = RecordingFetcher(
        ruyi_logger,
        urls,
        dest,
        {urls[0]: b"wrong", urls[1]: good},
    )

    fetcher.fetch(resume=True, post_fetch_validator=_accept_only(good, dest))

    assert fetcher.calls[0] == (urls[0], True)
    assert fetcher.calls[1] == (urls[1], False)
