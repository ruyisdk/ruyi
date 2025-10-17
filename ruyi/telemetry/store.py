from functools import cached_property
import json
import os
import pathlib
import re
import time
from typing import Callable, Final, Iterable
import uuid

from ..log import RuyiLogger
from ..utils.node_info import NodeInfo
from ..utils.url import urljoin_for_sure
from .aggregate import UploadPayload, aggregate_events
from .event import TelemetryEvent, is_telemetry_event
from .scope import TelemetryScope

# e.g. "run.202410201845.d06ca5d668e64fec833ed3e6eb926a2c.ndjson"
RE_RAW_EVENT_FILENAME: Final = re.compile(
    r"^run\.(?P<time_bucket>\d{12})\.(?P<uuid>[0-9a-f]{32})\.ndjson$"
)


def get_time_bucket(timestamp: int | float | time.struct_time | None = None) -> str:
    if timestamp is None:
        return time.strftime("%Y%m%d%H%M")
    elif isinstance(timestamp, float) or isinstance(timestamp, int):
        timestamp = time.localtime(timestamp)
    return time.strftime("%Y%m%d%H%M", timestamp)


def time_bucket_from_filename(filename: str) -> str | None:
    if m := RE_RAW_EVENT_FILENAME.match(filename):
        return m.group("time_bucket")
    return None


class TelemetryStore:
    def __init__(
        self,
        logger: RuyiLogger,
        scope: TelemetryScope,
        store_root: pathlib.Path,
        api_url: str | None = None,
        api_url_factory: Callable[[], str | None] | None = None,
    ) -> None:
        self._logger = logger
        self.scope = scope
        self.store_root = store_root
        self._api_url = api_url
        self._api_url_factory = api_url_factory

        self._events: list[TelemetryEvent] = []

    @cached_property
    def api_url(self) -> str | None:
        if u := self._api_url:
            return u
        if f := self._api_url_factory:
            return f()
        return None

    @property
    def raw_events_dir(self) -> pathlib.Path:
        return self.store_root / "raw"

    @property
    def upload_stage_dir(self) -> pathlib.Path:
        return self.store_root / "staged"

    @property
    def uploaded_dir(self) -> pathlib.Path:
        return self.store_root / "uploaded"

    @property
    def last_upload_marker_file(self) -> pathlib.Path:
        return self.store_root / ".stamp-last-upload"

    @property
    def last_upload_timestamp(self) -> float | None:
        try:
            return self.last_upload_marker_file.stat().st_mtime
        except FileNotFoundError:
            return None

    def record_upload_timestamp(self, time_now: float | None = None) -> None:
        if time_now is None:
            time_now = time.time()
        f = self.last_upload_marker_file
        f.touch()
        os.utime(f, (time_now, time_now))

    def record(self, kind: str, **params: object) -> None:
        self._events.append({"fmt": 1, "kind": kind, "params": params})

    def discard_events(self, v: bool = True) -> None:
        self._discard_events = v

    def persist(self, now: float | None = None) -> None:
        if not self._events:
            self._logger.D(f"scope {self.scope}: no event to persist")
            return

        now = time.time() if now is None else now

        self._logger.D(f"scope {self.scope}: flushing telemetry to persistent store")

        raw_events_dir = self.raw_events_dir
        raw_events_dir.mkdir(parents=True, exist_ok=True)

        # TODO: for now it is safe to not lock, because flush() is only ever
        # called at program exit time
        rough_time = get_time_bucket(now)
        rand = uuid.uuid4().hex
        batch_events_file = raw_events_dir / f"run.{rough_time}.{rand}.ndjson"
        with open(batch_events_file, "wb") as fp:
            for e in self._events:
                payload = json.dumps(e)
                fp.write(payload.encode("utf-8"))
                fp.write(b"\n")

        self._logger.D(
            f"scope {self.scope}: persisted {len(self._events)} telemetry event(s)"
        )

    def upload(self, installation_data: NodeInfo | None = None) -> None:
        self.prepare_data_for_upload(installation_data)
        self.upload_staged_payloads()

    def read_back_raw_events(self) -> Iterable[TelemetryEvent]:
        try:
            for f in self.raw_events_dir.glob("run.*.ndjson"):
                time_bucket = time_bucket_from_filename(f.name)
                with open(f, "r", encoding="utf-8", newline=None) as fp:
                    for line in fp:
                        try:
                            obj = json.loads(line)
                        except json.JSONDecodeError:
                            # losing some malformed telemetry events is okay
                            continue
                        if not is_telemetry_event(obj):
                            # ditto
                            continue
                        if time_bucket is not None and "time_bucket" not in obj:
                            obj["time_bucket"] = time_bucket
                        yield obj
        except FileNotFoundError:
            pass

    def purge_raw_events(self) -> None:
        files = list(self.raw_events_dir.glob("run.*.ndjson"))
        for f in files:
            f.unlink(missing_ok=True)

    def gen_upload_staging_filename(self, nonce: str) -> pathlib.Path:
        return self.upload_stage_dir / f"staged.{nonce}.json"

    def prepare_data_for_upload(self, installation_data: NodeInfo | None) -> None:
        # import ruyi.version here because this package is on the CLI startup
        # critical path, and version probing is costly there
        from ..version import RUYI_SEMVER

        aggregate_data = list(aggregate_events(self.read_back_raw_events()))

        payload_nonce = uuid.uuid4().hex  # for server-side dedup purposes
        payload: UploadPayload = {
            "fmt": 1,
            "nonce": payload_nonce,
            "ruyi_version": RUYI_SEMVER,
            "events": aggregate_data,
        }
        if installation_data is not None:
            payload["installation"] = installation_data

        dest_path = self.gen_upload_staging_filename(payload_nonce)
        self.upload_stage_dir.mkdir(parents=True, exist_ok=True)
        dest_path.write_text(json.dumps(payload), encoding="utf-8")

        self.purge_raw_events()

    def upload_staged_payloads(self) -> None:
        if not self.api_url:
            return

        try:
            staged_payloads = list(self.upload_stage_dir.glob("staged.*.json"))
        except FileNotFoundError:
            return

        try:
            self.uploaded_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            return

        for f in staged_payloads:
            self.upload_one_staged_payload(f, self.api_url)

        self.record_upload_timestamp()

    def upload_one_staged_payload(
        self,
        f: pathlib.Path,
        endpoint: str,
    ) -> None:
        # import ruyi.version here because this package is on the CLI startup
        # critical path, and version probing is costly there
        from ..version import RUYI_USER_AGENT

        api_path = urljoin_for_sure(endpoint, "upload-v1")
        self._logger.D(f"scope {self.scope}: about to upload payload {f} to {api_path}")

        import requests

        resp = requests.post(
            api_path,
            data=f.read_bytes(),
            headers={"User-Agent": RUYI_USER_AGENT},
            allow_redirects=True,
            timeout=5,
        )

        if not (200 <= resp.status_code < 300):
            self._logger.D(
                f"scope {self.scope}: telemetry upload failed: status code {resp.status_code}, content {resp.content.decode('utf-8', 'replace')}"
            )
            return

        self._logger.D(
            f"scope {self.scope}: telemetry upload ok: status code {resp.status_code}"
        )

        # move to completed dir
        # TODO: rotation
        try:
            f.rename(self.uploaded_dir / f.name)
        except OSError as e:
            self._logger.D(
                f"scope {self.scope}: failed to move uploaded payload away: {e}"
            )
