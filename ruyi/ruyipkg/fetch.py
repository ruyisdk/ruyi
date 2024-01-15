import abc
import subprocess
from typing import Self

from .. import log


class BaseFetcher:
    def __init__(self, urls: str | list[str], dest: str) -> None:
        if isinstance(urls, list):
            self.urls = urls
        elif isinstance(urls, str):
            self.urls = [urls]
        else:
            raise ValueError("urls must either be str or list[str]")

        self.dest = dest

    @classmethod
    @abc.abstractmethod
    def is_available(cls) -> bool:
        return False

    @abc.abstractmethod
    def fetch_one(self, url: str, dest: str, resume: bool) -> bool:
        return False

    def fetch(self, *, resume: bool = False) -> None:
        for url in self.urls:
            success = self.fetch_one(url, self.dest, resume)
            if success:
                return
            # add retry logic if necessary; right now this is not needed because
            # all fetcher commands handle retrying for us
        # all URLs have been tried and all have failed
        raise RuntimeError(
            f"failed to fetch '{self.dest}': all source URLs have failed"
        )

    @classmethod
    def new(cls, urls: str | list[str], dest: str) -> "BaseFetcher":
        return get_usable_fetcher_cls()(urls, dest)


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


class CurlFetcher(BaseFetcher):
    def __init__(self, urls: str | list[str], dest: str) -> None:
        super().__init__(urls, dest)

    @classmethod
    def is_available(cls) -> bool:
        # try running "curl --version" and it should succeed
        try:
            retcode = subprocess.call(["curl", "--version"], stdout=subprocess.DEVNULL)
            return retcode == 0
        except Exception as e:
            log.D(f"exception occurred when trying to curl --version:", e)
            return False

    def fetch_one(self, url: str, dest: str, resume: bool) -> bool:
        argv = ["curl"]
        if resume:
            argv.extend(("-C", "-"))
        argv.extend(
            (
                "--retry",
                "3",
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
            log.W(
                f"failed to fetch distfile: command '{' '.join(argv)}' returned {retcode}"
            )
            return False

        return True


register_fetcher(CurlFetcher)


class WgetFetcher(BaseFetcher):
    def __init__(self, urls: str | list[str], dest: str) -> None:
        super().__init__(urls, dest)

    @classmethod
    def is_available(cls) -> bool:
        # try running "wget --version" and it should succeed
        try:
            retcode = subprocess.call(["wget", "--version"], stdout=subprocess.DEVNULL)
            return retcode == 0
        except Exception as e:
            log.D(f"exception occurred when trying to wget --version:", e)
            return False

    def fetch_one(self, url: str, dest: str, resume: bool) -> bool:
        # These arguments are taken from Gentoo
        argv = ["wget"]
        if resume:
            argv.append("-c")
        argv.extend(("-t", "3", "-T", "60", "--passive-ftp", "-O", dest, url))

        retcode = subprocess.call(argv)
        if retcode != 0:
            log.W(
                f"failed to fetch distfile: command '{' '.join(argv)}' returned {retcode}"
            )
            return False

        return True


register_fetcher(WgetFetcher)
