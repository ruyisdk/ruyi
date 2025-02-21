import calendar
import json
import os
import pathlib
import re
import time
from typing import Final, Iterable, TYPE_CHECKING, cast
import uuid

import requests


from .. import log
from ..version import RUYI_SEMVER, RUYI_USER_AGENT
from ..utils.url import urljoin_for_sure
from .aggregate import UploadPayload, aggregate_events
from .event import TelemetryEvent, is_telemetry_event
from .node_info import NodeInfo, gather_node_info

if TYPE_CHECKING:
    # for avoiding circular import
    from ..config import GlobalConfig

FALLBACK_PM_TELEMETRY_ENDPOINT = "https://api.ruyisdk.cn/telemetry/pm/"

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


def next_utc_weekday(wday: int, now: float | None = None) -> int:
    t = time.gmtime(now)
    mday_delta = wday - t.tm_wday
    if mday_delta < 0:
        mday_delta += 7

    next_t = (
        t.tm_year,
        t.tm_mon,
        t.tm_mday + mday_delta,
        0,  # tm_hour
        0,  # tm_min
        0,  # tm_sec
        0,  # tm_wday
        0,  # tm_yday
        -1,  # tm_isdst
    )
    return calendar.timegm(next_t)


class TelemetryStore:
    def __init__(self, gc: "GlobalConfig") -> None:
        self.store_root = pathlib.Path(gc.telemetry_root)
        self.local_mode = gc.telemetry_mode == "local"
        self.upload_consent_time = gc.telemetry_upload_consent_time

        self.pm_api_url = FALLBACK_PM_TELEMETRY_ENDPOINT
        _pm_cfg_src = "fallback"
        if gc.override_pm_telemetry_url is not None:
            _pm_cfg_src = "local config"
            self.pm_api_url = gc.override_pm_telemetry_url
        else:
            for api_decl in gc.repo.config.telemetry_apis.values():
                if api_decl.get("scope", "") == "pm":
                    _pm_cfg_src = "repo"
                    self.pm_api_url = api_decl.get("url", "")
        log.D(
            f"configured PM telemetry endpoint via {_pm_cfg_src}: {self.pm_api_url or '(n/a)'}"
        )

        self._events: list[TelemetryEvent] = []
        self._discard_events = False

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
    def installation_file(self) -> pathlib.Path:
        return self.store_root / "installation.json"

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

    def init_installation(self, force_reinit: bool) -> NodeInfo | None:
        installation_file = self.installation_file
        if installation_file.exists() and not force_reinit:
            return self.read_installation_data()

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
        return installation_data

    def read_installation_data(self) -> NodeInfo | None:
        with open(self.installation_file, "rb") as fp:
            return cast(NodeInfo, json.load(fp))

    def upload_weekday(self) -> int | None:
        try:
            installation_data = self.read_installation_data()
        except FileNotFoundError:
            # init the node info if it's gone
            installation_data = self.init_installation(False)

        if installation_data is None:
            return None

        try:
            report_uuid_prefix = int(installation_data["report_uuid"][:8], 16)
        except ValueError:
            return None

        return report_uuid_prefix % 7  # 0 is Monday

    def has_upload_consent(self, time_now: float | None = None) -> bool:
        if self.upload_consent_time is None:
            return False
        if time_now is None:
            time_now = time.time()
        return self.upload_consent_time.timestamp() <= time_now

    def print_telemetry_notice(self, for_cli_verbose_output: bool = False) -> None:
        if self.local_mode:
            if for_cli_verbose_output:
                log.I(
                    "telemetry mode is [green]local[/]: local data collection only, no uploads"
                )
            return

        now = time.time()
        if self.has_upload_consent(now) and not for_cli_verbose_output:
            log.D("user has consented to telemetry upload")
            return

        upload_wday = self.upload_weekday()
        if upload_wday is None:
            return
        upload_wday_name = calendar.day_name[upload_wday]

        next_upload_day_ts = next_utc_weekday(upload_wday, now)
        next_upload_day = time.localtime(next_upload_day_ts)
        next_upload_day_end = time.localtime(next_upload_day_ts + 86400)
        next_upload_day_str = time.strftime("%Y-%m-%d %H:%M:%S %z", next_upload_day)
        next_upload_day_end_str = time.strftime(
            "%Y-%m-%d %H:%M:%S %z", next_upload_day_end
        )

        today_is_upload_day = self.is_upload_day(now)
        has_uploaded_today = self.has_uploaded_today(now)
        if for_cli_verbose_output:
            log.I(
                "telemetry mode is [green]on[/]: data is collected and periodically uploaded"
            )
            log.I(
                f"non-tracking usage information will be uploaded to RuyiSDK-managed servers [bold green]every {upload_wday_name}[/]"
            )
        else:
            log.W(
                f"this [yellow]ruyi[/] installation has telemetry mode set to [yellow]on[/], and [bold]will upload non-tracking usage information to RuyiSDK-managed servers[/] [bold green]every {upload_wday_name}[/]"
            )
        if today_is_upload_day:
            if has_uploaded_today:
                if last_upload_time := self.last_upload_timestamp:
                    last_upload_time_str = time.strftime(
                        "%Y-%m-%d %H:%M:%S %z", time.localtime(last_upload_time)
                    )
                    log.I(
                        f"usage information has already been uploaded today at {last_upload_time_str}"
                    )
                else:
                    log.I("usage information has already been uploaded sometime today")
            else:
                log.I("the next upload will happen [bold green]today[/] if not already")
        else:
            log.I(
                f"the next upload will happen anytime [yellow]ruyi[/] is executed between [bold green]{next_upload_day_str}[/] and [bold green]{next_upload_day_end_str}[/]"
            )

        if not for_cli_verbose_output:
            log.I("in order to hide this banner:")
            log.I("- opt out with [yellow]ruyi telemetry optout[/]")
            log.I("- or give consent with [yellow]ruyi telemetry consent[/]")

    def next_upload_day(self, time_now: float | None = None) -> int | None:
        upload_wday = self.upload_weekday()
        if upload_wday is None:
            return None
        return next_utc_weekday(upload_wday, time_now)

    def is_upload_day(self, time_now: float | None = None) -> bool:
        if time_now is None:
            time_now = time.time()
        if upload_day := self.next_upload_day(time_now):
            return upload_day <= time_now
        return False

    def has_uploaded_today(self, time_now: float | None = None) -> bool:
        if time_now is None:
            time_now = time.time()
        if upload_day := self.next_upload_day(time_now):
            upload_day_end = upload_day + 86400
            if last_upload_time := self.last_upload_timestamp:
                return upload_day <= last_upload_time < upload_day_end
        return False

    def record(self, kind: str, **params: object) -> None:
        self._events.append({"fmt": 1, "kind": kind, "params": params})

    def discard_events(self, v: bool = True) -> None:
        self._discard_events = v

    def flush(self, *, upload_now: bool = False) -> None:
        now = time.time()

        # We may be self-uninstalling and purging all state data, and in this
        # case we don't want to record anything (thus re-creating directories).
        if self._discard_events:
            log.D("discarding collected telemetry data")
            return

        log.D("flushing telemetry to persistent store")

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

        log.D(f"persisted {len(self._events)} telemetry event(s)")

        # try to upload if upload_now is True, or:
        #
        # * we're not in local mode
        # * today is the day
        # * we haven't uploaded today
        if not upload_now and (
            self.local_mode
            or not self.is_upload_day(now)
            or self.has_uploaded_today(now)
        ):
            return

        self.prepare_data_for_upload()
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

    def prepare_data_for_upload(self) -> None:
        try:
            installation_data = self.read_installation_data()
        except FileNotFoundError:
            # should not happen due to is_upload_day() initializing it for us
            # beforehand, but proceed without node info nonetheless
            installation_data = None

        aggregate_data = list(aggregate_events(self.read_back_raw_events()))

        payload_nonce = uuid.uuid4().hex  # for server-side dedup purposes
        payload: UploadPayload = {
            "fmt": 1,
            "nonce": payload_nonce,
            "ruyi_version": str(RUYI_SEMVER),
            "installation": installation_data,
            "events": aggregate_data,
        }

        dest_path = self.gen_upload_staging_filename(payload_nonce)
        self.upload_stage_dir.mkdir(parents=True, exist_ok=True)
        dest_path.write_text(json.dumps(payload), encoding="utf-8")

        self.purge_raw_events()

    def upload_staged_payloads(self) -> None:
        if self.local_mode or not self.pm_api_url:
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
            self.upload_one_staged_payload(f, self.pm_api_url)

        self.record_upload_timestamp()

    def upload_one_staged_payload(
        self,
        f: pathlib.Path,
        endpoint: str,
    ) -> None:
        api_path = urljoin_for_sure(endpoint, "upload-v1")
        log.D(f"about to upload payload {f} to {api_path}")

        resp = requests.post(
            api_path,
            data=f.read_bytes(),
            headers={"User-Agent": RUYI_USER_AGENT},
            allow_redirects=True,
            timeout=5,
        )

        if not (200 <= resp.status_code < 300):
            log.D(
                f"telemetry upload failed: status code {resp.status_code}, content {resp.content.decode('utf-8', 'replace')}"
            )
            return

        log.D(f"telemetry upload ok: status code {resp.status_code}")

        # move to completed dir
        # TODO: rotation
        try:
            f.rename(self.uploaded_dir / f.name)
        except OSError as e:
            log.D(f"failed to move uploaded payload away: {e}")
