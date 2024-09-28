import json
import pathlib
import time
from typing import TypedDict
import uuid

from .. import log
from .node_info import gather_node_info


class TelemetryEvent(TypedDict):
    fmt: int
    kind: str
    params: dict[str, object]


class TelemetryStore:
    def __init__(self, store_root: str, local: bool) -> None:
        self.store_root = pathlib.Path(store_root)
        self.local = local
        self._events: list[TelemetryEvent] = []

    @property
    def raw_events_dir(self) -> pathlib.Path:
        return self.store_root / "raw"

    def init_installation(self, force_reinit: bool) -> None:
        installation_file = self.store_root / "installation.json"
        if installation_file.exists() and not force_reinit:
            return

        # either this is a fresh installation or we're forcing a refresh
        installation_id = uuid.uuid4()
        log.D(
            f"initializing telemetry data store, installation_id={installation_id.hex}"
        )
        self.store_root.mkdir(parents=True, exist_ok=True)

        # (over)write installation data
        installation_data = gather_node_info(installation_id)
        with open(installation_file, "wb") as fp:
            fp.write(json.dumps(installation_data).encode("utf-8"))

    def record(self, kind: str, **params: object) -> None:
        self._events.append({"fmt": 1, "kind": kind, "params": params})

    def flush(self) -> None:
        log.D("flushing telemetry to persistent store")

        raw_events_dir = self.raw_events_dir
        raw_events_dir.mkdir(parents=True, exist_ok=True)

        # TODO: for now it is safe to not lock, because flush() is only ever
        # called at program exit time
        rough_time = time.strftime("%Y%m%d%H%M")
        rand = uuid.uuid4().hex
        batch_events_file = raw_events_dir / f"run.{rough_time}.{rand}.ndjson"
        with open(batch_events_file, "wb") as fp:
            for e in self._events:
                payload = json.dumps(e)
                fp.write(payload.encode("utf-8"))
                fp.write(b"\n")

        log.D(f"persisted {len(self._events)} telemetry event(s)")
