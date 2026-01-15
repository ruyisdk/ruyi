#!/usr/bin/env python3

import sys
import time

# import these common stdlib modules beforehand, to help reduce clutter
# these must be modules that does not significantly affect the ruyi CLI's
# startup performance
STDLIBS_TO_PRELOAD = [
    "argparse",
    "bz2",
    "datetime",
    "functools",
    "itertools",
    "lzma",
    "pathlib",
    "platform",
    "shutil",
    "typing",
    "os",
    "zlib",
]

if sys.version_info >= (3, 14):
    STDLIBS_TO_PRELOAD.append("annotationlib")

CURRENT_ALLOWLIST = {
    "ruyi",
    "ruyi.cli",
    "ruyi.cli.builtin_commands",
    "ruyi.cli.cmd",
    "ruyi.cli.completion",
    "ruyi.cli.config_cli",
    "ruyi.cli.self_cli",
    "ruyi.cli.version_cli",
    "ruyi.device",
    "ruyi.device.provision_cli",
    "ruyi.i18n",
    "ruyi.mux",
    "ruyi.mux.venv",
    "ruyi.mux.venv.venv_cli",
    "ruyi.pluginhost",
    "ruyi.pluginhost.plugin_cli",
    "ruyi.ruyipkg",
    "ruyi.ruyipkg.admin_cli",
    "ruyi.ruyipkg.cli_completion",  # part of the argparse machinery
    "ruyi.ruyipkg.entity_cli",
    "ruyi.ruyipkg.host",  # light-weight enough
    "ruyi.ruyipkg.install_cli",
    "ruyi.ruyipkg.list_cli",
    "ruyi.ruyipkg.list_filter",  # part of the argparse machinery
    "ruyi.ruyipkg.news_cli",
    "ruyi.ruyipkg.profile_cli",
    "ruyi.ruyipkg.update_cli",
    "ruyi.telemetry",
    "ruyi.telemetry.telemetry_cli",
    "ruyi.utils",
    "ruyi.utils.global_mode",  # light-weight enough
}


def main() -> int:
    for lib in STDLIBS_TO_PRELOAD:
        __import__(lib)

    before = set(sys.modules.keys())
    a = time.monotonic_ns()

    from ruyi.cli import builtin_commands

    b = time.monotonic_ns()
    print(f"Import of built-in commands took {((b - a) / 1_000_000):.2f} ms.")
    del builtin_commands

    after = set(sys.modules.keys())
    modules_brought_in = after - before
    unwanted_modules = modules_brought_in - CURRENT_ALLOWLIST
    if not unwanted_modules:
        return 0

    print(
        """\
Some previously unneeded modules are now imported during built-in commands
initialization:
"""
    )
    for module in sorted(unwanted_modules):
        print(f"  - {module}")
    print(
        """
Please assess the impact on CLI startup performance before:

- allowing the module(s) by revising this script, or
- deferring the import(s) so they do not slow down CLI startup.
"""
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
