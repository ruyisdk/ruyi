import io

from elftools.elf.elffile import ELFFile

from tests.ruyipkg.abi._elfbuilder import build_elf


def test_builder_roundtrips_via_pyelftools() -> None:
    # pyelftools dispatches SHT_RISCV_ATTRIBUTES (0x70000003) to
    # RISCVAttributesSection, whose __init__ asserts the first byte is the
    # 'A' format version. Prefix the arbitrary payload accordingly so the
    # section constructs and its raw data still roundtrips unchanged.
    payload = b"A\x02\x03\x04"
    data = build_elf(e_machine=243, sections={".riscv.attributes": (0x70000003, payload)})
    elf = ELFFile(io.BytesIO(data))
    assert elf.header["e_machine"] == "EM_RISCV"
    assert elf.elfclass == 64
    assert elf.little_endian is True
    sec = elf.get_section_by_name(".riscv.attributes")
    assert sec is not None
    assert sec.data() == payload


def test_builder_sets_e_type() -> None:
    data = build_elf(e_machine=62, e_type=3)
    elf = ELFFile(io.BytesIO(data))
    assert elf.header["e_type"] == "ET_DYN"
    assert elf.header["e_machine"] == "EM_X86_64"
