import argparse

from ruyi.cli.completer import NoneCompleter


def test_none_completer_returns_empty_iterable() -> None:
    """NoneCompleter must return an empty list, not None.

    argcomplete iterates over the completer's return value across all
    supported versions: as a list comprehension in 2.0.0 and a for loop
    in 3.x.  A None return causes TypeError (not iterable), silently
    crashing completion.  An empty list is safe to iterate and produces
    no suggestions.
    """
    nc = NoneCompleter()
    result = nc(
        prefix="",
        action=argparse.Action([], ""),
        parser=argparse.ArgumentParser(),
        parsed_args=argparse.Namespace(),
    )

    assert isinstance(result, list), f"expected list, got {type(result).__name__}"
    assert result == [], f"expected empty list, got {result!r}"

    # Simulate what argcomplete does: iterate over the result.
    completions = [c for c in result]
    assert completions == [], "iterating over result should yield nothing"
