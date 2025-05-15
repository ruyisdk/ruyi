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


class TelemetryScope:
    def __init__(self, repo_name: str | None) -> None:
        self._repo_name = repo_name

    def __repr__(self) -> str:
        return f"TelemetryScope(repo_name={self._repo_name})"

    def __str__(self) -> str:
        if self._repo_name:
            return f"repo:{self._repo_name}"
        return "pm"

    @property
    def repo_name(self) -> str | None:
        return self._repo_name

    @property
    def is_pm(self) -> bool:
        return self._repo_name is None
