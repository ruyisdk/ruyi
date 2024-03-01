import os
import subprocess
import sys


def main():
    vers = get_versions()
    print(f"Project SemVer       : {vers['semver']}")
    print(f"Nuitka version to use: {vers['nuitka_ver']}")
    sys.stdout.flush()

    nuitka_args = (
        # https://stackoverflow.com/questions/64761870/python-subprocess-doesnt-inherit-virtual-environment
        sys.executable,  # "python",
        "-m",
        "nuitka",
        "--standalone",
        "--onefile",
        "--assume-yes-for-downloads",
        "--output-filename=ruyi",
        "--output-dir=/build",
        "--no-deployment-flag=self-execution",
        f"--product-version={vers['nuitka_ver']}",
        f"--onefile-tempdir-spec={{CACHE_DIR}}/ruyi/progcache/{vers['semver']}",
        "--include-package=pygments.formatters",
        "--include-package=pygments.lexers",
        "--include-package=pygments.styles",
        "--windows-icon-from-ico=resources/ruyi.ico",
        "./ruyi/__main__.py",
    )

    subprocess.run(nuitka_args)


if __name__ == "__main__":
    # import the dist version helper
    script_dir = os.path.dirname(__file__)
    sys.path.append(script_dir)
    from _dist_version_helper import get_versions

    os.chdir(os.path.join(script_dir, ".."))
    main()
