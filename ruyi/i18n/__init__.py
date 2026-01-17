from io import BytesIO
import gettext
import os
import sys
from typing import Final, Mapping, NewType

if sys.version_info >= (3, 11):
    from typing import LiteralString
else:
    try:
        from typing_extensions import LiteralString
    except ImportError:
        # Python and typing_extensions both too old, which is unfortunately
        # the case with Ubuntu 22.04 LTS system packages.
        #
        # We don't expect development work within such an environment, so just
        # alias to str.
        LiteralString = str  # type: ignore[misc]

from ..resource_bundle import get_resource_blob


def _probe_lang(environ: Mapping[str, str]) -> list[str]:
    """Probe the environment variables the gettext way, to determine the list
    of preferred languages."""
    languages: list[str] = []
    # check the variables in this order
    for envar in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        if val := environ.get(envar):
            languages = val.split(":")
            break
    if "C" not in languages:
        languages.append("C")

    for i, lang in enumerate(languages):
        # normalize things like en_US.UTF-8 to en_US
        if "." in lang:
            languages[i] = lang.split(".", 1)[0]

    return languages


_DOMAINS = (
    "argparse",
    "ruyi",
)
"""gettext domains we supply and use ourselves"""


class I18nAdapter:
    """Adapter for gettext translation functions."""

    def __init__(self) -> None:
        self._t = gettext.NullTranslations()

    def hook(self) -> None:
        # monkey-patch the global gettext functions
        # the type ignore comments are necessary because mypy doesn't see
        # the bounded methods as compatible with the unbound functions
        # (it doesn't remove self from the unbound method signature)
        gettext.gettext = self.gettext  # type: ignore[assignment]
        gettext.ngettext = self.ngettext  # type: ignore[assignment]

    def init_from_env(self, environ: Mapping[str, str] | None = None) -> None:
        if environ is None:
            environ = os.environ

        for lang in _probe_lang(environ):
            for domain in _DOMAINS:
                if self.set_locale(domain, lang):
                    break

        # Fallback to null translations
        self._t = gettext.NullTranslations()

    def _get_mo(self, domain: str, locale: str) -> BytesIO | None:
        # this is always forward-slash-separated, because this is not a concrete
        # filesystem path, rather a resource bundle key
        path = f"locale/{locale}/LC_MESSAGES/{domain}.mo"
        blob = get_resource_blob(path)
        if blob:
            return BytesIO(blob)
        return None

    def set_locale(self, domain: str, locale: str | None = None) -> bool:
        if locale is not None:
            if mo_file := self._get_mo(domain, locale):
                self._t = gettext.GNUTranslations(mo_file)
                return True
        return False

    def gettext(self, x: str) -> str:
        return self._t.gettext(x)

    def ngettext(self, singular: str, plural: str, n: int) -> str:
        return self._t.ngettext(singular, plural, n)


ADAPTER: Final = I18nAdapter()


DeferredI18nString = NewType("DeferredI18nString", str)


def _(x: LiteralString | DeferredI18nString) -> str:
    """``gettext`` alias that ensures its input is string literal via type
    signature."""
    return ADAPTER.gettext(x)


def d_(x: LiteralString) -> DeferredI18nString:
    """Mark a string literal for deferred translation: call ``_`` at use sites."""
    return DeferredI18nString(x)
