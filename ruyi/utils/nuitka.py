import os


def get_nuitka_self_exe() -> str:
    try:
        # Assume we're a Nuitka onefile build, so our parent process is the onefile
        # bootstrap process. The onefile bootstrapper puts "our path" in the
        # undocumented environment variable $NUITKA_ONEFILE_BINARY, which works
        # on both Linux and Windows.
        return os.environ["NUITKA_ONEFILE_BINARY"]
    except KeyError:
        # It seems we are instead launched from the extracted onefile tempdir.
        # Assume our name is "ruyi" in this case; directory is available in
        # Nuitka metadata.
        import ruyi

        return os.path.join(ruyi.__compiled__.containing_dir, "ruyi")
