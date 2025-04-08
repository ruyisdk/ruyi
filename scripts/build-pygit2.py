#!/usr/bin/env python3

import os
import platform
import shutil
import subprocess
import sys
from typing import cast

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

PYGIT2_SETUPTOOLS_PATCH = """
--- a/build.sh
+++ b/build.sh
@@ -82,6 +82,8 @@ if [ "$CIBUILDWHEEL" = "1" ]; then
 else
     # Create a virtual environment
     $PYTHON -m venv $PREFIX
+    # install setuptools in the venv for python3.12+
+    $PREFIX/bin/pip install -U setuptools
     cd ci
 fi
 
"""

PYGIT2_OPENSSL_NO_DOCS_PATCH = """
--- a/build.sh
+++ b/build.sh
@@ -134,7 +134,7 @@ if [ -n "$OPENSSL_VERSION" ]; then
         # Linux
         tar xf $FILENAME.tar.gz
         cd $FILENAME
-        ./Configure shared --prefix=$PREFIX --libdir=$PREFIX/lib
+        ./Configure shared no-docs --prefix=$PREFIX --libdir=$PREFIX/lib
         make
         make install
         OPENSSL_PREFIX=$(pwd)
"""


def get_pygit2_src_uri(tag: str) -> tuple[str, str]:
    filename = f"{tag}.tar.gz"
    return (filename, f"https://github.com/libgit2/pygit2/archive/refs/tags/{filename}")


def log(s: str, fgcolor: int = 32, group: bool = False) -> None:
    # we cannot import rich because this script is executed before
    # `poetry install` in the dist build process
    print(f"\x1b[1;{fgcolor}m{s}\x1b[m", file=sys.stderr, flush=True)
    if group:
        begin_group(s)


def is_in_gha() -> bool:
    return "GITHUB_ACTIONS" in os.environ


def begin_group(title: str) -> None:
    if is_in_gha():
        print(f"::group::{title}", flush=True)


def end_group() -> None:
    if is_in_gha():
        print("::endgroup::", flush=True)


def main() -> None:
    build_root = os.environ["RUYI_DIST_BUILD_DIR"]

    workdir = os.path.join(build_root, "ruyi-pygit2")
    ensure_dir(workdir)

    cache_root = os.environ["RUYI_DIST_CACHE_DIR"]
    ensure_dir(cache_root)

    pygit2_ver = get_pygit2_version()
    log(f"resolved pygit2 version {pygit2_ver}")

    pygit2_cache_rev = 1  # bump this to force rebuild (e.g. for bumping indirect deps)
    pygit2_wheel_path = ensure_pygit2_wheel(
        pygit2_ver,
        workdir,
        cache_root,
        pygit2_cache_rev,
    )

    # this will print a header suitable for our logging purposes
    begin_group("pip install the pygit2 wheel")
    subprocess.run(("pip", "install", pygit2_wheel_path), check=True)
    end_group()

    log("informing poetry about the wheel", group=True)
    subprocess.run(("poetry", "add", "--lock", pygit2_wheel_path), check=True)
    end_group()


def ensure_dir(d: str) -> None:
    try:
        os.mkdir(d)
    except FileExistsError:
        pass


def ensure_pygit2_wheel(ver: str, workdir: str, cache_root: str, cache_rev: int) -> str:
    cache_key = get_cache_key("pygit2", ver, cache_rev)
    cache_dir = os.path.join(cache_root, cache_key)
    try:
        wheel_file = [
            i for i in os.listdir(cache_dir) if os.path.splitext(i)[1] == ".whl"
        ][0]
        wheel_path = os.path.join(cache_dir, wheel_file)
        log(f"found cached pygit2 (cache rev {cache_rev}) at {wheel_path}")
    except (FileNotFoundError, IndexError):
        log(f"cached pygit2 (cache rev {cache_rev}) not found, building")
        wheel_path = build_pygit2(ver, workdir)

        log(f"caching built wheel {wheel_path} to {cache_dir}")
        ensure_dir(cache_dir)

        dest_path = os.path.join(cache_dir, os.path.basename(wheel_path))
        shutil.copyfile(wheel_path, dest_path)

    return wheel_path


def build_pygit2(pygit2_ver: str, workdir: str) -> str:
    pygit2_tag = f"v{pygit2_ver}"
    pygit2_src_filename, pygit2_src_uri = get_pygit2_src_uri(pygit2_tag)
    pygit2_workdir = os.path.join(workdir, f"pygit2-{pygit2_ver}")

    # download the source
    log(f"downloading {pygit2_src_uri}", group=True)
    subprocess.run(
        ("wget", "-O", pygit2_src_filename, pygit2_src_uri),
        cwd=workdir,
        check=True,
    )
    end_group()

    # unpack the source
    log(f"unpacking {pygit2_src_filename}")
    subprocess.run(("tar", "-xf", pygit2_src_filename), cwd=workdir, check=True)

    log("patching pygit2 for Python 3.12+ builds")
    subprocess.run(
        ("patch", "-Np1"),
        cwd=pygit2_workdir,
        input=PYGIT2_SETUPTOOLS_PATCH.encode("utf-8"),
        check=True,
    )

    log("disabling docs generation during pygit2 openssl build")
    subprocess.run(
        ("patch", "-Np1"),
        cwd=pygit2_workdir,
        input=PYGIT2_OPENSSL_NO_DOCS_PATCH.encode("utf-8"),
        check=True,
    )

    # build wheel
    extra_env = get_pygit2_wheel_build_env(pygit2_workdir)
    log("extra envvar(s):", fgcolor=36)
    for k, v in extra_env.items():
        log(f"  {k}: {v}", fgcolor=36)
        os.environ[k] = v

    log("building pygit2 wheel", group=True)
    subprocess.run(
        ("sh", "build.sh", "wheel", "bundle"),
        cwd=pygit2_workdir,
        check=True,
    )
    end_group()

    pygit2_distdir = os.path.join(pygit2_workdir, "wheelhouse")
    pygit2_wheel_name = find_built_wheel_name_in(pygit2_distdir)
    return os.path.join(pygit2_distdir, pygit2_wheel_name)


def get_pygit2_version() -> str:
    # assume CWD is project root, which is guaranteed to be the case (see
    # end of file)
    with open("poetry.lock", "rb") as fp:
        info = tomllib.load(fp)

    pygit2 = [pkg for pkg in info["package"] if pkg["name"] == "pygit2"][0]
    return cast(str, pygit2["version"])


def get_pygit2_wheel_build_env(pygit2_dir: str) -> dict[str, str]:
    with open(os.path.join(pygit2_dir, "pyproject.toml"), "rb") as fp:
        pyproject = tomllib.load(fp)

    r: dict[str, str] = pyproject["tool"]["cibuildwheel"]["environment"]
    if "LIBGIT2" in r:
        # this is unnecessary
        del r["LIBGIT2"]

    if platform.machine() == "riscv64":
        # auditwheel 6.1.0+ has manylinux policies for riscv64, but the default
        # is too low for our environment
        # bump it up
        r["AUDITWHEEL_PLAT"] = "manylinux_2_35_riscv64"

    return r


def find_built_wheel_name_in(path: str) -> str:
    return [x for x in os.listdir(path) if os.path.splitext(x)[1] == ".whl"][0]


def get_cache_key(pkg_name: str, version: str, cache_rev: int) -> str:
    return f"{pkg_name}-{version}-cache{cache_rev}"


if __name__ == "__main__":
    # cd to project root
    os.chdir(os.path.join(os.path.dirname(__file__), ".."))
    main()
