import struct

from ruyi.ruyipkg.abi.interp.x86_64 import X86_64Interpreter
from ruyi.ruyipkg.abi.model import GnuProperty


def _isa_needed(mask: int) -> GnuProperty:
    return GnuProperty(0xC0008002, struct.pack("<I", mask).hex(), False)


def test_level_v3() -> None:
    interp = X86_64Interpreter()
    out = interp.interpret([_isa_needed(0b0111)], [], little_endian=True)
    assert out["isa_level"] == "v3"


def test_absent_property_is_baseline() -> None:
    assert (
        X86_64Interpreter().interpret([], [], little_endian=True)["isa_level"] == "v1"
    )


def test_rollup_minimum_level() -> None:
    interp = X86_64Interpreter()
    out = interp.rollup([{"isa_level": "v3"}, {"isa_level": "v2"}])
    assert out["isa_level"] == "v2"
    assert out["isa_levels"] == ["v2", "v3"]


_V2 = {"cx16", "lahf_lm", "popcnt", "pni", "sse4_1", "sse4_2", "ssse3"}
_V3 = {"avx", "avx2", "bmi1", "bmi2", "f16c", "fma", "movbe", "osxsave", "xsave"}
_V4 = {"avx512f", "avx512bw", "avx512cd", "avx512dq", "avx512vl"}


def _cpuinfo(flags: set[str]) -> str:
    return "processor\t: 0\nflags\t\t: fpu " + " ".join(sorted(flags)) + "\n"


def test_host_attrs_levels() -> None:
    interp = X86_64Interpreter()
    assert interp.host_attrs(cpuinfo=_cpuinfo(set())) == {"isa_level": "v1"}
    assert interp.host_attrs(cpuinfo=_cpuinfo(_V2 | _V3 | {"abm"})) == {
        "isa_level": "v3"
    }
    assert interp.host_attrs(cpuinfo=_cpuinfo(_V2 | _V3 | _V4 | {"lzcnt"})) == {
        "isa_level": "v4"
    }


def test_host_attrs_v2_needs_lzcnt_alias() -> None:
    interp = X86_64Interpreter()
    # v2 flag set alone, with neither abm nor lzcnt, is not enough.
    assert interp.host_attrs(cpuinfo=_cpuinfo(_V2)) == {"isa_level": "v1"}
    assert interp.host_attrs(cpuinfo=_cpuinfo(_V2 | {"lzcnt"})) == {"isa_level": "v2"}
    assert interp.host_attrs(cpuinfo=_cpuinfo(_V2 | {"abm"} | _V3)) == {
        "isa_level": "v3"
    }


def test_check_level_leq() -> None:
    interp = X86_64Interpreter()
    assert interp.check({"isa_level": "v3"}, {"isa_level": "v2"}) is True
    assert interp.check({"isa_level": "v2"}, {"isa_level": "v3"}) is False
    assert interp.check({}, {"isa_level": "v2"}) is None


def test_check_unparsable_level_is_undetermined() -> None:
    interp = X86_64Interpreter()
    assert interp.check({"isa_level": "bogus"}, {"isa_level": "v2"}) is None
    assert interp.check({"isa_level": "v2"}, {"isa_level": "v"}) is None
