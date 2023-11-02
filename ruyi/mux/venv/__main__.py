#!/usr/bin/env python3
# Regenerates data.py from fresh contents.

import base64
import glob
import os.path
import zlib


def make_payload_from_file(path: str) -> str:
    with open(path, "rb") as fp:
        content = fp.read()

    return base64.b64encode(zlib.compress(content, 9)).decode("ascii")


def main() -> None:
    self_path = os.path.dirname(__file__)
    os.chdir(self_path)

    payloads = {f[:-6]: make_payload_from_file(f) for f in glob.iglob("*.jinja")}
    with open("data.py", "w") as fp:
        p = lambda *args: print(*args, file=fp)
        p("# NOTE: This file is auto-generated. DO NOT EDIT!")
        p("# Update by running the __main__.py alongside this file\n")

        p("TEMPLATES = {")
        for filename, payload in payloads.items():
            p(f'    "{filename}": b"{payload}",  # fmt: skip')
        p("}")


if __name__ == "__main__":
    main()
