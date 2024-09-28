import json
import pathlib
import uuid

from .. import log
from .node_info import gather_node_info


class TelemetryStore:
    def __init__(self, store_root: str, local: bool) -> None:
        self.store_root = pathlib.Path(store_root)
        self.local = local

    def init_installation(self, force_reinit: bool) -> None:
        installation_file = self.store_root / "installation.json"
        if installation_file.exists() and not force_reinit:
            return

        # either this is a fresh installation or we're forcing a refresh
        installation_id = uuid.uuid4()
        log.D(f"initializing telemetry data store, installation_id={installation_id.hex}")
        self.store_root.mkdir(parents=True, exist_ok=True)

        # (over)write installation data
        installation_data = gather_node_info(installation_id)
        with open(installation_file, "wb") as fp:
            fp.write(json.dumps(installation_data).encode("utf-8"))

    def flush(self) -> None:
        log.D("flushing telemetry to persistent store")

        # TODO
