import tomlkit

from ruyi.utils.toml import (
    extract_footer_comments,
    extract_header_comments,
)


def test_extract_header_comments() -> None:
    a1 = """[foo]
    a = 2
    """
    assert extract_header_comments(tomlkit.parse(a1)) == []

    a2 = """

# foo

# bar

a = 2
# baz
"""

    assert extract_header_comments(tomlkit.parse(a2)) == [
        "# foo\n",
        "\n",
        "# bar\n",
        "\n",
    ]

    a3 = """
# baz
# quux

[a]
b = 2
"""

    assert extract_header_comments(tomlkit.parse(a3)) == ["# baz\n", "# quux\n", "\n"]


def test_extract_footer_comments() -> None:
    a1 = """[foo]
    a = 2
    """
    assert extract_footer_comments(tomlkit.parse(a1)) == []

    a2 = """
a = 2
# foo
# bar
"""

    assert extract_footer_comments(tomlkit.parse(a2)) == ["# foo\n", "# bar\n"]

    a3 = """# foo

# bar

[a]
foo = 2

# baz
# baz2

# quux
"""

    assert extract_footer_comments(tomlkit.parse(a3)) == [
        "\n",
        "# baz\n",
        "# baz2\n",
        "\n",
        "# quux\n",
    ]
