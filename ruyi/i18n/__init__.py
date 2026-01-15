import sys
from typing import NewType

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


def gettext(x: str) -> str:
    """Placeholder gettext function."""
    return x


DeferredI18nString = NewType("DeferredI18nString", str)


def _(x: LiteralString | DeferredI18nString) -> str:
    """``gettext`` alias that ensures its input is string literal via type
    signature."""
    return gettext(x)


def d_(x: LiteralString) -> DeferredI18nString:
    """Mark a string literal for deferred translation: call ``_`` at use sites."""
    return DeferredI18nString(x)
