import abc
import subprocess
from typing import Self

from .. import log


class BaseFetcher:
    def __init__(self, url: str, dest: str) -> None:
        self.url = url
        self.dest = dest

    @classmethod
    @abc.abstractmethod
    def is_available(cls) -> bool:
        return False

    @abc.abstractmethod
    def fetch(self, *, resume: bool = False) -> None:
        raise NotImplementedError

    @classmethod
    def new(cls, url: str, dest: str) -> Self:
        return get_usable_fetcher_cls()(url, dest)


KNOWN_FETCHERS: list[type[BaseFetcher]] = []


def register_fetcher(f: type[BaseFetcher]) -> None:
    # NOTE: can add priority support if needed
    KNOWN_FETCHERS.append(f)


_FETCHER_CACHE_POPULATED: bool = False
_CACHED_USABLE_FETCHER_CLASS: type[BaseFetcher] | None = None


def get_usable_fetcher_cls() -> type[BaseFetcher]:
    global _FETCHER_CACHE_POPULATED
    global _CACHED_USABLE_FETCHER_CLASS

    if _FETCHER_CACHE_POPULATED:
        if _CACHED_USABLE_FETCHER_CLASS is None:
            raise RuntimeError("no fetcher is available on the system")
        return _CACHED_USABLE_FETCHER_CLASS

    _FETCHER_CACHE_POPULATED = True
    for cls in KNOWN_FETCHERS:
        if cls.is_available():
            _CACHED_USABLE_FETCHER_CLASS = cls
            return cls

    raise RuntimeError("no fetcher is available on the system")


class WgetFetcher(BaseFetcher):
    def __init__(self, url: str, dest: str) -> None:
        super().__init__(url, dest)

    @classmethod
    def is_available(cls) -> bool:
        # try running "wget --version" and it should succeed
        try:
            retcode = subprocess.call(["wget", "--version"], stdout=subprocess.DEVNULL)
            return retcode == 0
        except Exception as e:
            log.D(f"exception occurred when trying to wget --version:", e)
            return False

    def fetch(self, *, resume: bool = False) -> None:
        # These arguments are taken from Gentoo
        argv = ["wget"]
        if resume:
            argv.append("-c")
        argv.extend(("-t", "3", "-T", "60", "--passive-ftp", "-O", self.dest, self.url))

        retcode = subprocess.call(argv)
        if retcode != 0:
            raise RuntimeError(
                f"failed to fetch distfile: command '{' '.join(argv)}' returned {retcode}"
            )


register_fetcher(WgetFetcher)
