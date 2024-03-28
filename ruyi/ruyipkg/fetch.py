import abc
import os
import subprocess

from .. import log

ENV_OVERRIDE_FETCHER = "RUYI_OVERRIDE_FETCHER"


class BaseFetcher:
    def __init__(self, urls: list[str], dest: str) -> None:
        self.urls = urls
        self.dest = dest

    @classmethod
    @abc.abstractmethod
    def is_available(cls) -> bool:
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
                log.I(f"retrying download ({t + 1} of {retries} times)")
            if self.fetch_one(url, dest, resume):
                return True
        return False

    def fetch(self, *, resume: bool = False, retries: int = 3) -> None:
        for url in self.urls:
            log.I(f"downloading {url} to {self.dest}")
            if self.fetch_one_with_retry(url, self.dest, resume, retries):
                return
        # all URLs have been tried and all have failed
        raise RuntimeError(
            f"failed to fetch '{self.dest}': all source URLs have failed"
        )

    @classmethod
    def new(cls, urls: list[str], dest: str) -> "BaseFetcher":
        return get_usable_fetcher_cls()(urls, dest)


KNOWN_FETCHERS: dict[str, type[BaseFetcher]] = {}


def register_fetcher(name: str, f: type[BaseFetcher]) -> None:
    # NOTE: can add priority support if needed
    KNOWN_FETCHERS[name] = f


_fetcher_cache_populated: bool = False
_cached_usable_fetcher_class: type[BaseFetcher] | None = None


def get_usable_fetcher_cls() -> type[BaseFetcher]:
    global _fetcher_cache_populated
    global _cached_usable_fetcher_class

    if _fetcher_cache_populated:
        if _cached_usable_fetcher_class is None:
            raise RuntimeError("no fetcher is available on the system")
        return _cached_usable_fetcher_class

    _fetcher_cache_populated = True

    if override_name := os.environ.get(ENV_OVERRIDE_FETCHER):
        log.D(f"forcing fetcher '{override_name}'")

        cls = KNOWN_FETCHERS.get(override_name)
        if cls is None:
            raise RuntimeError(f"unknown fetcher '{override_name}'")
        if not cls.is_available():
            raise RuntimeError(
                f"the requested fetcher '{override_name}' is unavailable on the system"
            )
        _cached_usable_fetcher_class = cls
        return cls

    for name, cls in KNOWN_FETCHERS.items():
        if not cls.is_available():
            log.D(f"fetcher '{name}' is unavailable")
            continue
        _cached_usable_fetcher_class = cls
        return cls

    raise RuntimeError("no fetcher is available on the system")


class CurlFetcher(BaseFetcher):
    def __init__(self, urls: list[str], dest: str) -> None:
        super().__init__(urls, dest)

    @classmethod
    def is_available(cls) -> bool:
        # try running "curl --version" and it should succeed
        try:
            retcode = subprocess.call(["curl", "--version"], stdout=subprocess.DEVNULL)
            return retcode == 0
        except Exception as e:
            log.D("exception occurred when trying to curl --version:", e)
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
            log.W(
                f"failed to fetch distfile: command '{' '.join(argv)}' returned {retcode}"
            )
            return False

        return True


register_fetcher("curl", CurlFetcher)


class WgetFetcher(BaseFetcher):
    def __init__(self, urls: list[str], dest: str) -> None:
        super().__init__(urls, dest)

    @classmethod
    def is_available(cls) -> bool:
        # try running "wget --version" and it should succeed
        try:
            retcode = subprocess.call(["wget", "--version"], stdout=subprocess.DEVNULL)
            return retcode == 0
        except Exception as e:
            log.D("exception occurred when trying to wget --version:", e)
            return False

    def fetch_one(self, url: str, dest: str, resume: bool) -> bool:
        # These arguments are taken from Gentoo
        argv = ["wget"]
        if resume:
            argv.append("-c")
        argv.extend(("-T", "60", "--passive-ftp", "-O", dest, url))

        retcode = subprocess.call(argv)
        if retcode != 0:
            log.W(
                f"failed to fetch distfile: command '{' '.join(argv)}' returned {retcode}"
            )
            return False

        return True


register_fetcher("wget", WgetFetcher)
