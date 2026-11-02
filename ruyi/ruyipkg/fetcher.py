import abc
import mmap
import os
import subprocess
from typing import Any, Callable, Final

import requests
from rich import progress

from ..i18n import _
from ..log import RuyiLogger

ENV_OVERRIDE_FETCHER: Final = "RUYI_OVERRIDE_FETCHER"


def _is_url_ftp(url: str) -> bool:
    return url.lower().startswith("ftp://")


def _is_url_http(url: str) -> bool:
    return url.lower().startswith(("http://", "https://"))


def _parse_http_code(stdout: str) -> str | None:
    """Extract the HTTP status code printed by ``curl --write-out``."""

    code = stdout.strip()
    # curl reports 000 when no HTTP response was received, e.g. for FTP
    # transfers or connection failures
    if len(code) != 3 or not code.isdigit() or code == "000":
        return None
    return code


def _remove_if_exists(path: str) -> None:
    try:
        os.remove(path)
    except FileNotFoundError:
        pass


_ACCESS_DENIED_CODES: Final = frozenset({"401", "403", "407", "429", "451", "511"})

# wget's documented exit statuses for authentication and server errors
_WGET_EXIT_AUTH_ERROR: Final = 6
_WGET_EXIT_SERVER_ERROR: Final = 8

# a resume request that starts beyond the remote object's length
_HTTP_RANGE_NOT_SATISFIABLE: Final = "416"

# connect and read timeout for the requests-based fetcher, in seconds
_DOWNLOAD_TIMEOUT: Final = 60


def _is_http_success_code(code: str) -> bool:
    return code.startswith("2")


def _http_error_warning(url: str, code: str) -> str:
    if code in _ACCESS_DENIED_CODES:
        return _(
            "failed to fetch distfile: '{url}' returned HTTP {code}; this may be caused by your network location (VPN/proxy exit), by the server's access policy, or by bot protection"
        ).format(
            url=url,
            code=code,
        )
    if code.startswith("5"):
        return _(
            "failed to fetch distfile: '{url}' returned HTTP {code}; this usually indicates a problem on the server side"
        ).format(
            url=url,
            code=code,
        )
    return _("failed to fetch distfile: '{url}' returned HTTP {code}").format(
        url=url,
        code=code,
    )


def _server_error_warning(url: str) -> str:
    """Warning for backends that do not expose the HTTP status code."""

    return _(
        "failed to fetch distfile: '{url}': the server returned an error response; this may be an access restriction or a server-side problem"
    ).format(
        url=url,
    )


def _curl_failure_warning(
    url: str,
    argv: list[str],
    retcode: int,
    code: str | None,
) -> str:
    # A non-zero exit with a 2xx status means the transfer broke after the
    # response headers arrived; reporting it as an HTTP error would be
    # misleading, since the status itself was fine.
    if code is not None and not _is_http_success_code(code):
        return _http_error_warning(url, code)
    return _("failed to fetch distfile: command '{cmd}' returned {retcode}").format(
        cmd=" ".join(argv),
        retcode=retcode,
    )


def _fetch_exception_warning(url: str, exc: requests.RequestException) -> str:
    if exc.response is not None and not _is_http_success_code(
        str(exc.response.status_code)
    ):
        return _http_error_warning(url, str(exc.response.status_code))
    return _("failed to fetch distfile: '{url}': {reason}").format(
        url=url,
        reason=exc,
    )


class BaseFetcher:
    def __init__(self, logger: RuyiLogger, urls: list[str], dest: str) -> None:
        self._logger = logger
        self.urls = urls
        self.dest = dest

    @classmethod
    @abc.abstractmethod
    def is_available(cls, logger: RuyiLogger) -> bool:
        return False

    @abc.abstractmethod
    def fetch_one(self, url: str, dest: str, resume: bool) -> bool:
        return False

    def fetch_one_with_retry(
        self,
        url: str,
        dest: str,
        resume: bool,
        retries: int,
    ) -> bool:
        for t in range(retries):
            if t > 0:
                self._logger.I(
                    _("retrying download ({current} of {total} times)").format(
                        current=t + 1,
                        total=retries,
                    )
                )
            if self.fetch_one(url, dest, resume):
                return True
        return False

    def fetch(
        self,
        *,
        resume: bool = False,
        retries: int = 3,
        post_fetch_validator: Callable[[], bool] | None = None,
    ) -> None:
        # A download that exits successfully is not necessarily a good file: a
        # mirror may serve an HTTP 200 error/redirect page, a truncated body, or
        # otherwise wrong content. When a validator is supplied (e.g. a checksum
        # check), a URL that downloads but fails validation is treated as failed
        # so we fall through to the next mirror instead of giving up.
        #
        # See: https://github.com/ruyisdk/ruyi/issues/498
        for url in self.urls:
            self._logger.I(
                _("downloading {url} to {dest}").format(
                    url=url,
                    dest=self.dest,
                )
            )
            if not self.fetch_one_with_retry(url, self.dest, resume, retries):
                continue
            if post_fetch_validator is not None and not post_fetch_validator():
                # the downloaded file is bad and has been discarded by the
                # validator, so any partial file is gone: do not try to resume
                # from the next mirror
                resume = False
                continue
            return
        # all URLs have been tried and all have failed
        raise RuntimeError(
            _("failed to fetch '{dest}': all source URLs have failed").format(
                dest=self.dest,
            )
        )

    @classmethod
    def new(cls, logger: RuyiLogger, urls: list[str], dest: str) -> "BaseFetcher":
        return get_usable_fetcher_cls(logger)(logger, urls, dest)


KNOWN_FETCHERS: Final[dict[str, type[BaseFetcher]]] = {}


def register_fetcher(name: str, f: type[BaseFetcher]) -> None:
    # NOTE: can add priority support if needed
    KNOWN_FETCHERS[name] = f


_fetcher_cache_populated: bool = False
_cached_usable_fetcher_class: type[BaseFetcher] | None = None


def get_usable_fetcher_cls(logger: RuyiLogger) -> type[BaseFetcher]:
    global _fetcher_cache_populated
    global _cached_usable_fetcher_class

    if _fetcher_cache_populated:
        if _cached_usable_fetcher_class is None:
            raise RuntimeError(_("no fetcher is available on the system"))
        return _cached_usable_fetcher_class

    _fetcher_cache_populated = True

    if override_name := os.environ.get(ENV_OVERRIDE_FETCHER):
        logger.D(f"forcing fetcher '{override_name}'")

        cls = KNOWN_FETCHERS.get(override_name)
        if cls is None:
            raise RuntimeError(
                _("unknown fetcher '{name}'").format(
                    name=override_name,
                )
            )
        if not cls.is_available(logger):
            raise RuntimeError(
                _("the requested fetcher '{name}' is unavailable on the system").format(
                    name=override_name,
                )
            )
        _cached_usable_fetcher_class = cls
        return cls

    for name, cls in KNOWN_FETCHERS.items():
        if not cls.is_available(logger):
            logger.D(f"fetcher '{name}' is unavailable")
            continue
        _cached_usable_fetcher_class = cls
        return cls

    raise RuntimeError(_("no fetcher is available on the system"))


class CurlFetcher(BaseFetcher):
    def __init__(self, logger: RuyiLogger, urls: list[str], dest: str) -> None:
        super().__init__(logger, urls, dest)

    @classmethod
    def is_available(cls, logger: RuyiLogger) -> bool:
        # try running "curl --version" and it should succeed
        try:
            retcode = subprocess.call(["curl", "--version"], stdout=subprocess.DEVNULL)
            return retcode == 0
        except Exception as e:
            logger.D("exception occurred when trying to curl --version:", e)
            return False

    def fetch_one(self, url: str, dest: str, resume: bool) -> bool:
        argv = ["curl"]
        if resume:
            argv.extend(("-C", "-"))

        # A bug in curl 8.14.1 (and only that version) broke the recognition of
        # the `--ftp-pasv`` flag, and unfortunately this version is currently
        # provided by some popular distros so far.
        #
        # So, for the vast majority of non-FTP downloads to work even with
        # this buggy version, we simply do not pass the flag if the URL is
        # not an FTP one.
        #
        # See: https://github.com/curl/curl/issues/17545
        # See: https://github.com/ruyisdk/ruyi/issues/316
        if _is_url_ftp(url):
            argv.append("--ftp-pasv")

        # `--fail` makes curl exit with an error on HTTP statuses >= 400
        # instead of saving the response body as if it were the file we
        # asked for.  The status code is still reported on stdout via
        # `--write-out`, so we can tell the user what the server said.
        #
        # See: https://github.com/ruyisdk/ruyi/issues/506
        argv.extend(
            (
                "-L",
                "--fail",
                "--connect-timeout",
                "60",
                # give up on a transfer that makes no meaningful progress,
                # so that a stalled server does not block mirror fallback
                "--speed-limit",
                "1",
                "--speed-time",
                "60",
                "--write-out",
                "%{http_code}",
                "-o",
                dest,
                url,
            )
        )

        proc = subprocess.run(argv, stdout=subprocess.PIPE, text=True)
        code = _parse_http_code(proc.stdout)

        if proc.returncode != 0:
            self._logger.W(_curl_failure_warning(url, argv, proc.returncode, code))
            # A failed fresh download may have left an error body or an
            # empty file behind (e.g. 401 with some auth schemes), and that
            # must not be mistaken for a partial download later on.  Keep
            # partials from ordinary transfer failures, and keep the file
            # when resuming, where curl does not write the error response
            # and the existing partial is still worth continuing from.
            if not resume and code is not None and not _is_http_success_code(code):
                _remove_if_exists(dest)
            return False

        # Be defensive even if curl exits successfully: an unfollowed
        # redirect or a misbehaving proxy can still yield a non-2xx final
        # status, and curl does not consider every such response a failure
        # (e.g. 3xx without a Location header, or 401/407 with some auth
        # schemes).  Whatever body it wrote is not the distfile, so drop it,
        # including any pre-existing partial that it may have been appended
        # to.
        #
        # The one exception is a 416 while resuming: curl leaves the partial
        # untouched, and the next mirror may still be able to continue from
        # it, so keep it.
        if _is_url_http(url) and code is not None and not _is_http_success_code(code):
            self._logger.W(_http_error_warning(url, code))
            if not (resume and code == _HTTP_RANGE_NOT_SATISFIABLE):
                _remove_if_exists(dest)
            return False

        return True


register_fetcher("curl", CurlFetcher)


class WgetFetcher(BaseFetcher):
    def __init__(self, logger: RuyiLogger, urls: list[str], dest: str) -> None:
        super().__init__(logger, urls, dest)

    @classmethod
    def is_available(cls, logger: RuyiLogger) -> bool:
        # try running "wget --version" and it should succeed
        try:
            retcode = subprocess.call(["wget", "--version"], stdout=subprocess.DEVNULL)
            return retcode == 0
        except Exception as e:
            logger.D("exception occurred when trying to wget --version:", e)
            return False

    def fetch_one(self, url: str, dest: str, resume: bool) -> bool:
        # These arguments are taken from Gentoo
        argv = ["wget"]
        if resume:
            argv.append("-c")
        # wget does not suffer from the same bug as curl, but to be safe, we
        # also enable the passive FTP mode only if the URL is an FTP one.
        if _is_url_ftp(url):
            argv.append("--passive-ftp")
        argv.extend(("-T", "60", "-O", dest, url))

        retcode = subprocess.call(argv)
        if retcode != 0:
            if retcode in (_WGET_EXIT_AUTH_ERROR, _WGET_EXIT_SERVER_ERROR):
                # On a fresh download wget truncates the output file before
                # it learns about the error response, leaving an empty file
                # behind.  With -c it leaves an existing partial untouched,
                # and that one is still useful for resuming.
                if not resume:
                    _remove_if_exists(dest)
                self._logger.W(_server_error_warning(url))
                return False

            self._logger.W(
                _(
                    "failed to fetch distfile: command '{cmd}' returned {retcode}"
                ).format(
                    cmd=" ".join(argv),
                    retcode=retcode,
                )
            )
            return False

        # wget still exits successfully for a few non-2xx responses, such as
        # a 300 without a Location header, and its status cannot be inspected
        # without capturing stderr, which would disable its progress display.
        # Distfile always runs a checksum check afterwards, so such a body is
        # rejected there instead.
        return True


register_fetcher("wget", WgetFetcher)


class PythonRequestsFetcher(BaseFetcher):
    def __init__(self, logger: RuyiLogger, urls: list[str], dest: str) -> None:
        super().__init__(logger, urls, dest)

        self.chunk_size = 4 * mmap.PAGESIZE
        # TODO: User-Agent

    @classmethod
    def is_available(cls, logger: RuyiLogger) -> bool:
        return True

    def fetch_one(self, url: str, dest: str, resume: bool) -> bool:
        self._logger.D(f"downloading [cyan]{url}[/] to [cyan]{dest}")

        open_mode = "ab" if resume else "wb"
        start_from = 0
        headers: dict[str, str] = {}
        if resume:
            filesize = os.stat(dest).st_size
            self._logger.D(f"resuming from position {filesize}")
            start_from = filesize
            headers["Range"] = f"bytes={filesize}-"

        try:
            r = requests.get(
                url,
                headers=headers,
                stream=True,
                timeout=(_DOWNLOAD_TIMEOUT, _DOWNLOAD_TIMEOUT),
            )
        except requests.RequestException as exc:
            self._logger.W(_fetch_exception_warning(url, exc))
            return False

        try:
            r.raise_for_status()
        except requests.RequestException as exc:
            # an HTTP error response is not the distfile, and the body must
            # not be kept either
            r.close()
            self._logger.W(_fetch_exception_warning(url, exc))
            return False

        # requests only raises for 4xx/5xx; an unfollowed redirect or a
        # broken proxy can still hand us a 3xx body
        if not _is_http_success_code(str(r.status_code)):
            r.close()
            self._logger.W(_http_error_warning(url, str(r.status_code)))
            return False

        total_len: int | None = None
        if total_len_str := r.headers.get("Content-Length"):
            total_len = int(total_len_str) + start_from

        try:
            trc = progress.TimeRemainingColumn(compact=True, elapsed_when_finished=True)  # type: ignore[call-arg,unused-ignore]
        except TypeError:
            # rich < 12.0.0 does not support the styles we're asking here, so
            # just downgrade UX in favor of basic usability in that case.
            #
            # see https://github.com/Textualize/rich/pull/1992
            trc = progress.TimeRemainingColumn()

        columns = (
            progress.SpinnerColumn(),
            progress.BarColumn(),
            progress.DownloadColumn(),
            progress.TransferSpeedColumn(),
            trc,
        )
        dest_filename = os.path.basename(dest)
        try:
            with open(dest, open_mode) as f:
                with progress.Progress(
                    *columns, console=self._logger.log_console
                ) as pg:
                    indeterminate = total_len is None
                    kwargs: dict[str, Any]
                    if indeterminate:
                        # be compatible with rich <= 12.3.0 where add_task()'s `total`
                        # parameter cannot be None
                        # see https://github.com/Textualize/rich/commit/052b15785876ad85
                        kwargs = {"start": False}
                    else:
                        kwargs = {"total": total_len}

                    task = pg.add_task(dest_filename, completed=start_from, **kwargs)
                    for chunk in r.iter_content(self.chunk_size):
                        f.write(chunk)
                        # according to the docs it's probably not okay to pulse the
                        # progress bar if the total number of steps is not yet known
                        if not indeterminate:
                            pg.advance(task, len(chunk))
        except requests.RequestException as exc:
            # keep the partial file, if any, so that the next attempt can
            # resume from where this one broke off
            self._logger.W(_fetch_exception_warning(url, exc))
            return False
        finally:
            r.close()

        return True


register_fetcher("requests", PythonRequestsFetcher)
