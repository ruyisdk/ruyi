import typing

if typing.TYPE_CHECKING:

    class NuitkaVersion(typing.NamedTuple):
        major: int
        minor: int
        micro: int
        releaselevel: str
        containing_dir: str
        standalone: bool
        onefile: bool
        macos_bundle_mode: bool
        no_asserts: bool
        no_docstrings: bool
        no_annotations: bool
        module: bool
        main: str
        original_argv0: str | None

    __compiled__: NuitkaVersion
