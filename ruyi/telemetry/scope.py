from typing import Literal, TypeAlias, TypeGuard

TelemetryScopeConfig: TypeAlias = Literal["pm"] | Literal["repo"]


def is_telemetry_scope_config(x: object) -> TypeGuard[TelemetryScopeConfig]:
    if not isinstance(x, str):
        return False
    match x:
        case "pm" | "repo":
            return True
        case _:
            return False
