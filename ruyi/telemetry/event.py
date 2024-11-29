from typing import TypedDict, TypeGuard, TYPE_CHECKING

if TYPE_CHECKING:
    from typing_extensions import NotRequired


class TelemetryEvent(TypedDict):
    fmt: int
    time_bucket: "NotRequired[str]"  # canonically "YYYYMMDDHHMM"
    kind: str
    params: dict[str, object]


def is_telemetry_event(x: object) -> TypeGuard[TelemetryEvent]:
    if not isinstance(x, dict):
        return False

    if not 3 <= len(x.keys()) <= 4:
        return False

    try:
        if not isinstance(x["fmt"], int):
            return False
        if not isinstance(x["kind"], str):
            return False
        if not isinstance(x["params"], dict):
            return False
    except KeyError:
        return False

    try:
        if not isinstance(x["time_bucket"], str):
            return False
        if len(x["time_bucket"]) != 12:
            return False
        if not x["time_bucket"].isdigit():
            return False
    except KeyError:
        pass

    return True
