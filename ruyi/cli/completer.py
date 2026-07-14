"""
helper functions for CLI completions
"""

import argparse
from typing import Protocol, Any, TYPE_CHECKING

if TYPE_CHECKING:
    # A "lie" for type checking purposes. This is a known and wont fix issue for mypy.
    # Mypy would think the fallback import needs to be the same type as the first import.
    # See: https://github.com/python/mypy/issues/1153
    from argcomplete.completers import BaseCompleter
else:
    try:
        from argcomplete.completers import BaseCompleter
    except ImportError:
        # Fallback for environments where argcomplete is less than 2.0.0
        class BaseCompleter(object):
            def __call__(
                self,
                *,
                prefix: str,
                action: argparse.Action,
                parser: argparse.ArgumentParser,
                parsed_args: argparse.Namespace,
            ) -> None:
                raise NotImplementedError(
                    "This method should be implemented by a subclass."
                )


class NoneCompleter(BaseCompleter):
    # The return type 'list[str]' deliberately deviates from the base class
    # annotation '-> None' in argcomplete (tested through 3.7.0).  Upstream's
    # @completers.BaseCompleter.__call__ has -> None, but finders.py:413-414
    # iterates over the return value with 'for completion in completer_output:'
    # (the non-Mapping branch), so returning None would raise TypeError at
    # runtime.  Returning an empty list is safe and produces no suggestions.
    def __call__(  # type: ignore[override]
        self,
        *,
        prefix: str,
        action: argparse.Action,
        parser: argparse.ArgumentParser,
        parsed_args: argparse.Namespace,
    ) -> list[str]:
        return []


class DynamicCompleter(Protocol):
    def __call__(
        self,
        prefix: str,
        parsed_args: object,
        **kwargs: Any,
    ) -> list[str]: ...
