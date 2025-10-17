from typing import Iterable, TypeAlias, TypedDict, TYPE_CHECKING

if TYPE_CHECKING:
    from typing_extensions import NotRequired

from ..utils.node_info import NodeInfo
from .event import TelemetryEvent


class AggregatedTelemetryEvent(TypedDict):
    time_bucket: str
    kind: str
    params: list[tuple[str, str]]
    count: int


class UploadPayload(TypedDict):
    fmt: int
    nonce: str
    ruyi_version: str
    installation: "NotRequired[NodeInfo | None]"
    events: list[AggregatedTelemetryEvent]


def stringify_param_val(v: object) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, bytes):
        return v.decode("utf-8")
    if isinstance(v, str):
        return v
    return str(v)


AggregateKey: TypeAlias = tuple[tuple[str, str], ...]


def _make_aggregate_key(ev: TelemetryEvent) -> AggregateKey:
    param_list = [(k, stringify_param_val(v)) for k, v in ev["params"].items()]
    param_list.sort()
    return tuple([("", ev["kind"])] + param_list)


def aggregate_events(
    events: Iterable[TelemetryEvent],
) -> Iterable[AggregatedTelemetryEvent]:
    # dict[time_bucket, dict[AggregateKey, count]]
    buf: dict[str, dict[AggregateKey, int]] = {}
    for raw_ev in events:
        time_bucket = raw_ev.get("time_bucket")
        if time_bucket is None:
            continue
        if time_bucket not in buf:
            buf[time_bucket] = {}

        agg_key = _make_aggregate_key(raw_ev)
        if agg_key not in buf[time_bucket]:
            buf[time_bucket][agg_key] = 1
        else:
            buf[time_bucket][agg_key] += 1

    for time_bucket in sorted(buf.keys()):
        bucket_events = buf[time_bucket]
        for agg_key in sorted(bucket_events.keys()):
            yield {
                "time_bucket": time_bucket,
                "kind": agg_key[0][1],
                "params": list(agg_key[1:]),
                "count": bucket_events[agg_key],
            }
