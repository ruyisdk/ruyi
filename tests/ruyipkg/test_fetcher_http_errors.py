"""Regression tests for HTTP error responses mistaken for distfiles.

See https://github.com/ruyisdk/ruyi/issues/506: a mirror answering a
download request with a 4xx/5xx status used to have its error page saved
as if it were the distfile, and the failure later surfaced as a bogus
integrity-check error.  These tests pin down that the fetch backends
treat non-2xx responses as fetch failures and never keep whatever the
server sent in that case.
"""

import os
from typing import Any, cast

import pytest
import requests

from ruyi.log import RuyiLogger
from ruyi.ruyipkg import fetcher as fetcher_mod
from ruyi.ruyipkg.fetcher import (
    CurlFetcher,
    PythonRequestsFetcher,
    WgetFetcher,
    _curl_failure_warning,
    _fetch_exception_warning,
    _http_error_warning,
)


class _FakeProcessResult:
    def __init__(self, returncode: int, stdout: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout


class _FakeSubprocess:
    """Stand-in for the ``subprocess`` module used by the fetchers."""

    PIPE = -1
    DEVNULL = -3

    def __init__(
        self,
        results: _FakeProcessResult | list[_FakeProcessResult],
        side_effect: Any = None,
    ) -> None:
        self.results = results if isinstance(results, list) else [results]
        self.side_effect = side_effect
        self.calls: list[list[str]] = []
        self.kwargs: list[dict[str, Any]] = []

    @property
    def argv(self) -> list[str]:
        return self.calls[-1]

    def run(self, argv: list[str], **kwargs: Any) -> _FakeProcessResult:
        self.calls.append(list(argv))
        self.kwargs.append(kwargs)
        if self.side_effect is not None:
            self.side_effect(argv)
        return self.results[min(len(self.calls) - 1, len(self.results) - 1)]

    def call(self, argv: list[str], **kwargs: Any) -> int:
        return self.run(argv, **kwargs).returncode


def _patch_subprocess(
    monkeypatch: pytest.MonkeyPatch,
    results: _FakeProcessResult | list[_FakeProcessResult],
    side_effect: Any = None,
) -> _FakeSubprocess:
    fake = _FakeSubprocess(results, side_effect)
    monkeypatch.setattr(fetcher_mod, "subprocess", fake)
    return fake


class _FakeResponse:
    def __init__(
        self,
        status_code: int,
        body: bytes = b"",
        raise_exc: Exception | None = None,
    ) -> None:
        self.status_code = status_code
        self.headers: dict[str, str] = {}
        self.closed = False
        self._body = body
        self._raise_exc = raise_exc

    def raise_for_status(self) -> None:
        if self._raise_exc is not None:
            raise self._raise_exc

    def iter_content(self, chunk_size: int) -> Any:
        yield self._body

    def close(self) -> None:
        self.closed = True

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *args: Any) -> None:
        return None


class _FailingStreamResponse(_FakeResponse):
    """A response whose body breaks off after the first chunk."""

    def iter_content(self, chunk_size: int) -> Any:
        yield b"partial"
        raise requests.ConnectionError("connection reset")


def test_curl_asks_curl_to_fail_on_http_errors(
    ruyi_logger: RuyiLogger,
    tmp_path: "os.PathLike[str]",
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dest = os.path.join(tmp_path, "distfile")
    fake = _patch_subprocess(monkeypatch, _FakeProcessResult(0, "200"))
    fetcher = CurlFetcher(ruyi_logger, ["https://mirror.example/pkg"], dest)

    assert fetcher.fetch_one("https://mirror.example/pkg", dest, False)
    assert "--fail" in fake.argv
    # the status code is needed for a useful message, so it must be
    # requested on stdout, where the response body does not go
    assert "%{http_code}" in fake.argv
    assert fake.kwargs[-1]["stdout"] == _FakeSubprocess.PIPE


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("200", True),
        ("206", True),
        ("300", False),
        ("404", False),
        ("502", False),
    ],
)
def test_curl_treats_non_2xx_status_as_failure(
    ruyi_logger: RuyiLogger,
    tmp_path: "os.PathLike[str]",
    monkeypatch: pytest.MonkeyPatch,
    status: str,
    expected: bool,
) -> None:
    # even if curl somehow exits 0, a non-2xx response is not a distfile
    dest = os.path.join(tmp_path, "distfile")
    _patch_subprocess(monkeypatch, _FakeProcessResult(0, status))
    fetcher = CurlFetcher(ruyi_logger, ["https://mirror.example/pkg"], dest)

    assert fetcher.fetch_one("https://mirror.example/pkg", dest, False) is expected


def test_curl_discards_body_written_for_non_2xx_response(
    ruyi_logger: RuyiLogger,
    tmp_path: "os.PathLike[str]",
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # curl does exit 0 for some non-2xx responses (e.g. an unfollowed
    # redirect), and the body ends up in the destination file
    dest = os.path.join(tmp_path, "distfile")

    def write_body(argv: list[str]) -> None:
        with open(dest, "wb") as f:
            f.write(b"<html>redirecting</html>")

    _patch_subprocess(monkeypatch, _FakeProcessResult(0, "300"), write_body)
    fetcher = CurlFetcher(ruyi_logger, ["https://mirror.example/pkg"], dest)

    assert not fetcher.fetch_one("https://mirror.example/pkg", dest, False)
    assert not os.path.exists(dest)


def test_curl_keeps_partial_file_when_resume_is_rejected(
    ruyi_logger: RuyiLogger,
    tmp_path: "os.PathLike[str]",
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # curl leaves the partial untouched on a 416, and the next mirror may
    # still be able to resume from it
    dest = os.path.join(tmp_path, "distfile")
    partial = b"HELLO"
    with open(dest, "wb") as f:
        f.write(partial)

    _patch_subprocess(monkeypatch, _FakeProcessResult(0, "416"))
    fetcher = CurlFetcher(ruyi_logger, ["https://mirror.example/pkg"], dest)

    assert not fetcher.fetch_one("https://mirror.example/pkg", dest, True)
    with open(dest, "rb") as f:
        assert f.read() == partial


def test_curl_does_not_mistake_ftp_placeholder_status_for_failure(
    ruyi_logger: RuyiLogger,
    tmp_path: "os.PathLike[str]",
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # curl reports 000 as the HTTP status for non-HTTP transfers
    dest = os.path.join(tmp_path, "distfile")
    _patch_subprocess(monkeypatch, _FakeProcessResult(0, "000"))
    url = "ftp://mirror.example/pkg"
    fetcher = CurlFetcher(ruyi_logger, [url], dest)

    assert fetcher.fetch_one(url, dest, False)


def test_curl_failure_warning_reports_http_status_when_there_is_one() -> None:
    warning = _curl_failure_warning("https://mirror.example/pkg", ["curl"], 22, "502")

    assert "HTTP 502" in warning
    assert "server side" in warning


def test_curl_failure_warning_does_not_report_a_2xx_status_as_http_error() -> None:
    # a transfer that dies after the headers has a 2xx status; that must
    # not be presented as an HTTP error
    warning = _curl_failure_warning("https://mirror.example/pkg", ["curl"], 18, "200")

    assert "HTTP" not in warning
    assert "returned 18" in warning


def test_wget_discards_file_left_behind_by_server_error(
    ruyi_logger: RuyiLogger,
    tmp_path: "os.PathLike[str]",
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dest = os.path.join(tmp_path, "distfile")

    def write_body(argv: list[str]) -> None:
        # wget truncates the output file before it learns the status
        with open(dest, "wb"):
            pass

    _patch_subprocess(monkeypatch, _FakeProcessResult(8), write_body)
    fetcher = WgetFetcher(ruyi_logger, ["https://mirror.example/pkg"], dest)

    assert not fetcher.fetch_one("https://mirror.example/pkg", dest, False)
    assert not os.path.exists(dest)


def test_wget_discards_file_left_behind_by_auth_error(
    ruyi_logger: RuyiLogger,
    tmp_path: "os.PathLike[str]",
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # a 401 makes wget leave an empty file behind, with exit code 6
    dest = os.path.join(tmp_path, "distfile")

    def write_body(argv: list[str]) -> None:
        with open(dest, "wb"):
            pass

    _patch_subprocess(monkeypatch, _FakeProcessResult(6), write_body)
    fetcher = WgetFetcher(ruyi_logger, ["https://mirror.example/pkg"], dest)

    assert not fetcher.fetch_one("https://mirror.example/pkg", dest, False)
    assert not os.path.exists(dest)


def test_wget_keeps_partial_file_on_network_failure(
    ruyi_logger: RuyiLogger,
    tmp_path: "os.PathLike[str]",
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # a dropped connection must still leave the partial file for resuming
    dest = os.path.join(tmp_path, "distfile")
    partial = b"partial contents"

    def write_partial(argv: list[str]) -> None:
        with open(dest, "wb") as f:
            f.write(partial)

    _patch_subprocess(monkeypatch, _FakeProcessResult(4), write_partial)
    fetcher = WgetFetcher(ruyi_logger, ["https://mirror.example/pkg"], dest)

    assert not fetcher.fetch_one("https://mirror.example/pkg", dest, False)
    with open(dest, "rb") as f:
        assert f.read() == partial


@pytest.mark.parametrize("retcode", [6, 8])
def test_wget_keeps_partial_file_when_resuming_after_server_error(
    ruyi_logger: RuyiLogger,
    tmp_path: "os.PathLike[str]",
    monkeypatch: pytest.MonkeyPatch,
    retcode: int,
) -> None:
    # with -c, wget leaves an existing partial untouched on an error response
    dest = os.path.join(tmp_path, "distfile")
    partial = b"HELLO"
    with open(dest, "wb") as f:
        f.write(partial)

    fake = _patch_subprocess(monkeypatch, _FakeProcessResult(retcode))
    fetcher = WgetFetcher(ruyi_logger, ["https://mirror.example/pkg"], dest)

    assert not fetcher.fetch_one("https://mirror.example/pkg", dest, True)
    assert "-c" in fake.argv
    with open(dest, "rb") as f:
        assert f.read() == partial


def test_requests_rejects_http_error_without_saving_body(
    ruyi_logger: RuyiLogger,
    tmp_path: "os.PathLike[str]",
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dest = os.path.join(tmp_path, "distfile")
    response = _FakeResponse(503, b"<html>maintenance</html>")
    exc = requests.HTTPError("503 Server Error", response=response)  # type: ignore[arg-type]
    response._raise_exc = exc
    monkeypatch.setattr(requests, "get", lambda *a, **kw: response)
    fetcher = PythonRequestsFetcher(ruyi_logger, ["https://mirror.example/pkg"], dest)

    assert not fetcher.fetch_one("https://mirror.example/pkg", dest, False)
    assert not os.path.exists(dest)
    assert response.closed


def test_requests_rejects_non_2xx_redirect(
    ruyi_logger: RuyiLogger,
    tmp_path: "os.PathLike[str]",
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # raise_for_status() does not fire for 3xx, and requests does not
    # follow a redirect without a Location header
    dest = os.path.join(tmp_path, "distfile")
    response = _FakeResponse(302, b"<html>redirecting</html>")
    monkeypatch.setattr(requests, "get", lambda *a, **kw: response)
    fetcher = PythonRequestsFetcher(ruyi_logger, ["https://mirror.example/pkg"], dest)

    assert not fetcher.fetch_one("https://mirror.example/pkg", dest, False)
    assert not os.path.exists(dest)
    assert response.closed


def test_requests_keeps_partial_file_when_body_breaks_off(
    ruyi_logger: RuyiLogger,
    tmp_path: "os.PathLike[str]",
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dest = os.path.join(tmp_path, "distfile")
    response = _FailingStreamResponse(200)
    monkeypatch.setattr(requests, "get", lambda *a, **kw: response)
    fetcher = PythonRequestsFetcher(ruyi_logger, ["https://mirror.example/pkg"], dest)

    assert not fetcher.fetch_one("https://mirror.example/pkg", dest, False)
    with open(dest, "rb") as f:
        assert f.read() == b"partial"
    assert response.closed


def test_requests_returns_false_on_connection_error(
    ruyi_logger: RuyiLogger,
    tmp_path: "os.PathLike[str]",
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dest = os.path.join(tmp_path, "distfile")

    def raise_connection_error(*args: Any, **kwargs: Any) -> Any:
        raise requests.ConnectionError("connection reset")

    monkeypatch.setattr(requests, "get", raise_connection_error)
    fetcher = PythonRequestsFetcher(ruyi_logger, ["https://mirror.example/pkg"], dest)

    assert not fetcher.fetch_one("https://mirror.example/pkg", dest, False)


def test_fetch_falls_through_to_next_url_on_http_error(
    ruyi_logger: RuyiLogger,
    tmp_path: "os.PathLike[str]",
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dest = os.path.join(tmp_path, "distfile")
    urls = ["https://bad.example/pkg", "https://good.example/pkg"]
    fake = _patch_subprocess(
        monkeypatch,
        [
            _FakeProcessResult(22, "502"),
            _FakeProcessResult(0, "200"),
        ],
    )
    fetcher = CurlFetcher(ruyi_logger, urls, dest)

    fetcher.fetch(retries=1)

    assert [call[-1] for call in fake.calls] == urls


def test_fetch_exception_warning_does_not_report_a_2xx_status_as_http_error() -> None:
    # a body that breaks off mid-transfer still carries the 2xx status of
    # the response headers, which is not the problem to report
    response = _FakeResponse(200)
    exc = requests.exceptions.ChunkedEncodingError(
        "connection broken",
        response=cast("requests.Response", response),
    )
    warning = _fetch_exception_warning("https://mirror.example/pkg", exc)

    assert "HTTP" not in warning
    assert "connection broken" in warning


def test_http_error_warning_blames_the_server_for_5xx() -> None:
    warning = _http_error_warning("https://mirror.example/pkg", "502")

    assert "502" in warning
    assert "server side" in warning


def test_http_error_warning_mentions_client_side_causes_for_denials() -> None:
    warning = _http_error_warning("https://mirror.example/pkg", "403")

    assert "403" in warning
    # a denial may well be caused by the user's network location or by
    # bot protection, not only by a broken mirror
    assert "VPN" in warning
    assert "bot protection" in warning
