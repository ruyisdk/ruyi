from ruyi.utils.templating import render_template_str


def test_templates_are_loaded_from_package_resources() -> None:
    result = render_template_str(
        "binfmt.conf",
        {
            "resolved_progs": [
                {
                    "display_name": "qemu-riscv64",
                    "env": {},
                    "binfmt_misc_str": ":qemu-riscv64:M::fake::/usr/bin/qemu-riscv64:",
                }
            ],
        },
    )

    assert "Emulator qemu-riscv64" in result
    assert ":qemu-riscv64:M::fake::/usr/bin/qemu-riscv64:" in result
