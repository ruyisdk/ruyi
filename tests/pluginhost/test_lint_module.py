import ast

import pytest

from ruyi.pluginhost.unsandboxed import lint_module


def _lint(src: str) -> None:
    lint_module(ast.parse(src))


def test_plain_module_passes() -> None:
    _lint(
        "x = 1\n"
        "def f(a, b):\n"
        "    return a + b\n"
        "y = [f(i, 1) for i in range(10)]\n"
    )


@pytest.mark.parametrize(
    ("src", "expected_feature"),
    [
        ("y = (x := 1)\n", "walrus"),
        ("raise ValueError('x')\n", "raise"),
        ("assert True\n", "assert"),
        ("import os\n", "import"),
        ("from os import path\n", "from"),
        ("try:\n    pass\nexcept Exception:\n    pass\n", "try"),
        ("with open('x') as f:\n    pass\n", "with"),
        (
            "match x:\n    case 1:\n        pass\n    case _:\n        pass\n",
            "match",
        ),
        ("def g():\n    yield 1\n", "yield"),
        ("def g():\n    yield from [1]\n", "yield from"),
        ("def g():\n    global x\n", "global"),
        (
            "def outer():\n"
            "    x = 1\n"
            "    def inner():\n"
            "        nonlocal x\n"
            "    return inner\n",
            "nonlocal",
        ),
        ("class C:\n    pass\n", "class"),
        ("async def g():\n    pass\n", "async def"),
        ("@staticmethod\ndef f():\n    pass\n", "decorator"),
        ("x: int = 1\n", "variable type annotation"),
        ("def f() -> int:\n    return 1\n", "return type annotation"),
        ("def f(x: int):\n    return x\n", "parameter type annotation"),
        ("x = f'hello {name}'\n", "f-string"),
        ("x = {1, 2, 3}\n", "set display"),
        ("x = {i for i in range(3)}\n", "set comprehension"),
        ("x = sum(i for i in range(3))\n", "generator expression"),
        ("x = [1]\ndel x\n", "del"),
        ("x = a @ b\n", "matrix-multiplication operator"),
        ("a @= b\n", "matrix-multiplication assignment"),
        ("ok = 0 <= i < n\n", "chained comparison"),
        ("def f(a, /, b):\n    return a + b\n", "positional-only parameter"),
        ("def f():\n    while True:\n        pass\n", "while"),
        # `await`, `async for`, `async with` can only occur syntactically
        # inside an `async def`, so they are shadowed by the `async def`
        # rejection above; they have their own ``visit_*`` overrides anyway
        # for defence in depth.
    ],
)
def test_gated_feature_is_rejected(src: str, expected_feature: str) -> None:
    with pytest.raises(RuntimeError) as excinfo:
        _lint(src)
    msg = str(excinfo.value)
    assert "is not allowed in plugin code" in msg
    assert expected_feature in msg
    assert "line " in msg
