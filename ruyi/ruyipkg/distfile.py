from functools import cached_property
import os
from typing import Any, Final

from ..log import RuyiLogger
from .checksum import Checksummer
from .fetcher import BaseFetcher
from .pkg_manifest import DistfileDecl
from .repo import MetadataRepo
from .unpack import do_unpack, do_unpack_or_symlink
from .unpack_method import UnpackMethod


# https://github.com/ruyisdk/ruyi/issues/46
HELP_ERROR_FETCHING: Final = """
Downloads can fail for a multitude of reasons, most of which should not and
cannot be handled by [yellow]Ruyi[/]. For your convenience though, please check if any
of the following common failure modes apply to you, and take actions
accordingly if one of them turns out to be the case:

* Basic connectivity problems
    - is [yellow]the gateway[/] reachable?
    - is [yellow]common websites[/] reachable?
    - is there any [yellow]DNS pollution[/]?
* Organizational and/or ISP restrictions
    - is there a [yellow]firewall[/] preventing Ruyi traffic?
    - is your [yellow]ISP blocking access[/] to the source website?
* Volatile upstream
    - is the recorded [yellow]link dead[/]? (Please raise a Ruyi issue for a fix!)
"""


class Distfile:
    def __init__(
        self,
        decl: DistfileDecl,
        mr: MetadataRepo,
    ) -> None:
        self._decl = decl
        self._mr = mr

    @cached_property
    def dest(self) -> str:
        destdir = self._mr.global_config.ensure_distfiles_dir()
        return os.path.join(destdir, self._decl.name)

    @property
    def size(self) -> int:
        return self._decl.size

    @property
    def csums(self) -> dict[str, str]:
        return self._decl.checksums

    @property
    def prefixes_to_unpack(self) -> list[str] | None:
        return self._decl.prefixes_to_unpack

    @property
    def strip_components(self) -> int:
        return self._decl.strip_components

    @property
    def unpack_method(self) -> UnpackMethod:
        return self._decl.unpack_method

    @property
    def is_fetch_restricted(self) -> bool:
        return self._decl.is_restricted("fetch")

    @cached_property
    def urls(self) -> list[str]:
        return self._mr.get_distfile_urls(self._decl)

    def render_fetch_instructions(self, logger: RuyiLogger, lang_code: str) -> str:
        fr = self._decl.fetch_restriction
        if fr is None:
            return ""

        params = {
            "dest_path": self.dest,
        }
        if "params" in fr:
            for k in params.keys():
                # Don't allow package-defined params to override preset params,
                # to reduce surprises for packagers.
                if k in fr["params"]:
                    logger.F(
                        f"malformed package fetch instructions: the param named '{k}' is reserved and cannot be overridden by packages"
                    )
                    raise RuntimeError("malformed package fetch instructions")

            params.update(fr["params"])

        return self._mr.messages.render_message(fr["msgid"], lang_code, params)

    def is_downloaded(self) -> bool:
        """Check if the distfile has been downloaded. A return value of True
        does NOT guarantee integrity."""

        try:
            st = os.stat(self.dest)
            return st.st_size == self.size
        except FileNotFoundError:
            return False

    def ensure(self, logger: RuyiLogger) -> None:
        logger.D(f"checking {self.dest}")
        try:
            st = os.stat(self.dest)
        except FileNotFoundError:
            logger.D(f"file {self.dest} not existent")
            return self.fetch_and_ensure_integrity(logger)

        if st.st_size < self.size:
            # assume incomplete transmission, try to resume
            logger.D(
                f"file {self.dest} appears incomplete: size {st.st_size} < {self.size}; resuming"
            )
            return self.fetch_and_ensure_integrity(logger, resume=True)
        elif st.st_size == self.size:
            if self.ensure_integrity_or_rm(logger):
                logger.D(f"file {self.dest} passed checks")
                return

            # the file is already gone, re-fetch
            logger.D(f"re-fetching {self.dest}")
            return self.fetch_and_ensure_integrity(logger)

        logger.W(
            f"file {self.dest} is corrupt: size too big ({st.st_size} > {self.size}); deleting"
        )
        os.remove(self.dest)
        return self.fetch_and_ensure_integrity(logger)

    def ensure_integrity_or_rm(self, logger: RuyiLogger) -> bool:
        try:
            with open(self.dest, "rb") as fp:
                cs = Checksummer(fp, self.csums)
                cs.check()
                return True
        except ValueError as e:
            logger.W(f"file {self.dest} is corrupt: {e}; deleting")
            os.remove(self.dest)
            return False

    def fetch_and_ensure_integrity(
        self,
        logger: RuyiLogger,
        *,
        resume: bool = False,
    ) -> None:
        if self.is_fetch_restricted:
            # the file must be re-fetched if we arrive here, but we cannot,
            # because of the fetch restriction.
            #
            # notify the user and die
            # TODO: allow rendering instructions for all missing fetch-restricted
            # files at once
            logger.F(
                f"the file [yellow]'{self.dest}'[/] cannot be automatically fetched"
            )
            logger.I("instructions on fetching this file:")
            logger.I(
                self.render_fetch_instructions(logger, self._mr.global_config.lang_code)
            )
            raise SystemExit(1)

        try:
            return self._fetch_and_ensure_integrity(logger, resume=resume)
        except RuntimeError as e:
            logger.F(f"{e}")
            logger.stdout(HELP_ERROR_FETCHING)
            raise SystemExit(1)

    def _fetch_and_ensure_integrity(
        self,
        logger: RuyiLogger,
        *,
        resume: bool = False,
    ) -> None:
        fetcher = BaseFetcher.new(logger, self.urls, self.dest)
        fetcher.fetch(resume=resume)

        if not self.ensure_integrity_or_rm(logger):
            raise RuntimeError(
                f"failed to fetch distfile: {self.dest} failed integrity checks"
            )

    def unpack(
        self,
        root: str | os.PathLike[Any] | None,
        logger: RuyiLogger,
    ) -> None:
        return do_unpack(
            logger,
            self.dest,
            root,
            self.strip_components,
            self.unpack_method,
            prefixes_to_unpack=self.prefixes_to_unpack,
        )

    def unpack_or_symlink(
        self,
        root: str | os.PathLike[Any] | None,
        logger: RuyiLogger,
    ) -> None:
        return do_unpack_or_symlink(
            logger,
            self.dest,
            root,
            self.strip_components,
            self.unpack_method,
            prefixes_to_unpack=self.prefixes_to_unpack,
        )
