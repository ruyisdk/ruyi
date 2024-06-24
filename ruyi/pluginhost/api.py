from ruyi.cli.version import RUYI_SEMVER


class RuyiHostAPI:
    def __init__(self) -> None:
        pass

    @property
    def ruyi_version(self) -> str:
        return str(RUYI_SEMVER)

    @property
    def ruyi_plugin_api_rev(self) -> int:
        return 1


def ruyi_plugin_rev(rev: object) -> RuyiHostAPI:
    if not isinstance(rev, int):
        raise TypeError("rev must be int in ruyi_plugin_rev calls")
    if rev != 1:
        raise ValueError(
            f"Ruyi plugin API revision {rev} is not supported by this Ruyi"
        )
    return RuyiHostAPI()
