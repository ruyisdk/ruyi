#!/usr/bin/env python3

import argparse
import os
import pathlib
import sys

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

from babel.messages.frontend import CommandLineInterface


DOMAINS = (
    "argparse",
    "ruyi",
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Helper script for Ruyi i18n tasks.",
    )
    parser.add_argument(
        "action",
        choices=["refresh-pot", "init-po", "merge-po", "build-mo"],
        help="The action to perform.",
    )
    parser.add_argument(
        "-l",
        "--locale",
        type=str,
        help="Locale code (for init-po action).",
    )

    args = parser.parse_args()
    action: str = args.action
    locale: str | None = args.locale

    match action:
        case "refresh-pot":
            return _do_refresh_pot()
        case "init-po":
            if locale is None:
                print("fatal error: --locale must be specified for init-po action")
                return 1
            return _do_init_po(locale)
        case "merge-po":
            if locale is None:
                print("fatal error: --locale must be specified for merge-po action")
                return 1
            return _do_merge_po(locale)
        case "build-mo":
            if locale is None:
                print("fatal error: --locale must be specified for build-mo action")
                return 1
            return _do_build_mo(locale)
        case _:
            print(f"fatal error: unknown action '{action}'")
            return 1


def _query_project_version() -> str:
    # assume CWD is project root, which is guaranteed to be the case (see
    # end of file)
    with open("pyproject.toml", "rb") as fp:
        poetry2_project = tomllib.load(fp)
        r = poetry2_project["project"]["version"]

    if not isinstance(r, str):
        print("fatal error: project.version not a string")
        raise SystemExit(1)

    return r


def _invoke_babel(argv: list[str]) -> None:
    CommandLineInterface().run(argv)  # type: ignore[no-untyped-call]  # this part of babel lacks type information


def _do_refresh_pot() -> int:
    for domain in DOMAINS:
        if generator := POT_GENERATORS.get(domain):
            print(f"Refreshing POT for domain '{domain}'...")
            generator()
        else:
            print(f"fatal error: no POT generator for domain '{domain}'")
            return 1
    return 0


def _do_refresh_ruyi_pot() -> int:
    project_version = _query_project_version()

    babel_argv = [
        "pybabel",
        "extract",
        # general nice-to-have options
        "--no-wrap",
        "--sort-by-file",
        # project metadata
        "--msgid-bugs-address=https://github.com/ruyisdk/ruyi/issues",
        "--copyright-holder=Institute of Software, Chinese Academy of Sciences (ISCAS)",
        "--project=ruyi",
        f"--version={project_version}",
        # additionally recognize our deferred i18n marker
        "-k",
        "d_",
        # and our i18n note tag
        "-c",
        "i18n NOTE:",
        # output file
        "-o",
        "resources/po/ruyi.pot",
    ]

    # add all source files
    project_srcdir = pathlib.Path("ruyi")
    babel_argv.extend(str(x) for x in project_srcdir.rglob("*.py"))

    _invoke_babel(babel_argv)
    return 0


def _do_refresh_argparse_pot() -> int:
    babel_argv = [
        "pybabel",
        "extract",
        # general nice-to-have options
        "--no-wrap",
        "--sort-by-file",
        # no project metadata for argparse which is Python stdlib
        # output file
        "-o",
        "resources/po/argparse.pot",
        # add source file
        # for now this is only one file
        argparse.__file__,
    ]
    _invoke_babel(babel_argv)
    return 0


POT_GENERATORS = {
    "ruyi": _do_refresh_ruyi_pot,
    "argparse": _do_refresh_argparse_pot,
}


def _do_init_po(locale: str) -> int:
    for domain in DOMAINS:
        babel_argv = [
            "pybabel",
            "init",
            # project metadata
            f"--domain={domain}",
            "-l",
            locale,
            # same formatting as the POT
            "--no-wrap",
            # assume the POT file is already there
            "-i",
            f"resources/po/{domain}.pot",
            # destination
            "-d",
            "resources/po",
        ]
        _invoke_babel(babel_argv)
    return 0


def _do_merge_po(locale: str) -> int:
    for domain in DOMAINS:
        babel_argv = [
            "pybabel",
            "update",
            # project metadata
            f"--domain={domain}",
            "-l",
            locale,
            # same formatting as the POT
            "--no-wrap",
            # destination
            "-d",
            "resources/po",
            # input POT file
            "-i",
            f"resources/po/{domain}.pot",
        ]
        _invoke_babel(babel_argv)
    return 0


def _do_build_mo(locale: str) -> int:
    destdir = pathlib.Path("resources/bundled/locale") / locale / "LC_MESSAGES"
    destdir.mkdir(parents=True, exist_ok=True)

    for domain in DOMAINS:
        babel_argv = [
            "pybabel",
            "compile",
            "-f",
            "--statistics",
            # project metadata
            f"--domain={domain}",
            "-l",
            locale,
            # destination directory
            "-d",
            "resources/bundled/locale",
            # input file
            "-i",
            f"resources/po/{locale}/LC_MESSAGES/{domain}.po",
        ]
        _invoke_babel(babel_argv)

    # regenerate resource bundle data
    from ruyi.resource_bundle.__main__ import main as resource_bundle_main

    resource_bundle_main()

    return 0


if __name__ == "__main__":
    # cd to project root
    os.chdir(os.path.join(os.path.dirname(__file__), ".."))
    sys.exit(main())
