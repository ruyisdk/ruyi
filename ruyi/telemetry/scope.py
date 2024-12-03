from typing import Literal, TypeAlias, TypeGuard

TelemetryScope: TypeAlias = Literal["pm"] | Literal["repo"]


def is_telemetry_scope(x: object) -> TypeGuard[TelemetryScope]:
    if not isinstance(x, str):
        return False
    match x:
        case "pm" | "repo":
            return True
        case _:
            return False
