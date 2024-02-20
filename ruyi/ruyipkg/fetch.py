import abc
import subprocess

from .. import log


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


KNOWN_FETCHERS: list[type[BaseFetcher]] = []


def register_fetcher(f: type[BaseFetcher]) -> None:
    # NOTE: can add priority support if needed
    KNOWN_FETCHERS.append(f)


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
    for cls in KNOWN_FETCHERS:
        if cls.is_available():
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


register_fetcher(CurlFetcher)


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


register_fetcher(WgetFetcher)
