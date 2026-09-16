from ruyi.utils.pathmatch import build_matcher


def test_empty_matches_nothing() -> None:
    m = build_matcher([])
    assert not m.is_excluded("usr/bin/foo")


def test_basic_glob() -> None:
    m = build_matcher(["*.txt"])
    assert m.is_excluded("a.txt")
    assert m.is_excluded("sub/b.txt")
    assert not m.is_excluded("a.bin")


def test_doublestar_and_anchor() -> None:
    m = build_matcher(["/build/**"])
    assert m.is_excluded("build/x/y.so")
    assert not m.is_excluded("src/build/x")


def test_negation_last_match_wins() -> None:
    m = build_matcher(["tests/**", "!tests/keep.so"])
    assert m.is_excluded("tests/fixture.so")
    assert not m.is_excluded("tests/keep.so")


def test_directory_only_pattern() -> None:
    m = build_matcher(["fixtures/"])
    assert m.is_excluded("fixtures/data.bin")
