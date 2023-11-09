import os


def get_nuitka_self_exe() -> str:
    # Assume we're a Nuitka onefile build, so our parent process is the onefile
    # bootstrap process. We only care about Linux, and the Nuitka onefile bootstrap
    # code already requires `/proc` (it reads `/proc/self/exe` itself in order to mmap
    # itself), so we can just read `/proc/{os.getppid()}/exe` for getting "our path".
    parent_exe_link = f"/proc/{os.getppid()}/exe"
    return os.readlink(parent_exe_link)
