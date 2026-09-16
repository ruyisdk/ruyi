from ruyi.ruyipkg.abi.interp.base import get_interpreter, register


class _FakeInterp:
    e_machines = frozenset({0xBEEF})

    def interpret(self, gnu_properties, elf_attributes):  # type: ignore[no-untyped-def]
        return {"ok": True}

    def rollup(self, per_file):  # type: ignore[no-untyped-def]
        return {}


def test_unknown_machine_returns_none() -> None:
    assert get_interpreter(0x0FFF) is None


def test_register_and_lookup() -> None:
    register(_FakeInterp())
    got = get_interpreter(0xBEEF)
    assert got is not None
    assert got.interpret([], []) == {"ok": True}
