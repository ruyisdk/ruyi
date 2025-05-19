import abc
import mmap
import os
import subprocess
from typing import Any, Final

import requests
from rich import progress

from ..log import RuyiLogger

ENV_OVERRIDE_FETCHER: Final = "RUYI_OVERRIDE_FETCHER"


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
                self._logger.I(f"retrying download ({t + 1} of {retries} times)")
            if self.fetch_one(url, dest, resume):
                return True
        return False

    def fetch(self, *, resume: bool = False, retries: int = 3) -> None:
        for url in self.urls:
            self._logger.I(f"downloading {url} to {self.dest}")
            if self.fetch_one_with_retry(url, self.dest, resume, retries):
                return
        # all URLs have been tried and all have failed
        raise RuntimeError(
            f"failed to fetch '{self.dest}': all source URLs have failed"
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
            raise RuntimeError("no fetcher is available on the system")
        return _cached_usable_fetcher_class

    _fetcher_cache_populated = True

    if override_name := os.environ.get(ENV_OVERRIDE_FETCHER):
        logger.D(f"forcing fetcher '{override_name}'")

        cls = KNOWN_FETCHERS.get(override_name)
        if cls is None:
            raise RuntimeError(f"unknown fetcher '{override_name}'")
        if not cls.is_available(logger):
            raise RuntimeError(
                f"the requested fetcher '{override_name}' is unavailable on the system"
            )
        _cached_usable_fetcher_class = cls
        return cls

    for name, cls in KNOWN_FETCHERS.items():
        if not cls.is_available(logger):
            logger.D(f"fetcher '{name}' is unavailable")
            continue
        _cached_usable_fetcher_class = cls
        return cls

    raise RuntimeError("no fetcher is available on the system")


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
        argv.extend(
            (
                "-L",
                "--connect-timeout",
                "60",
                "--ftp-pasv",
                "-o",
                dest,
                url,
            )
        )

        retcode = subprocess.call(argv)
        if retcode != 0:
            self._logger.W(
                f"failed to fetch distfile: command '{' '.join(argv)}' returned {retcode}"
            )
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
        argv.extend(("-T", "60", "--passive-ftp", "-O", dest, url))

        retcode = subprocess.call(argv)
        if retcode != 0:
            self._logger.W(
                f"failed to fetch distfile: command '{' '.join(argv)}' returned {retcode}"
            )
            return False

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

        r = requests.get(url, headers=headers, stream=True)
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
        with open(dest, open_mode) as f:
            with progress.Progress(*columns, console=self._logger.log_console) as pg:
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

        return True


register_fetcher("requests", PythonRequestsFetcher)
