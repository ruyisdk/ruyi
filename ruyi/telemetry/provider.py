import calendar
import datetime
import functools
import json
import pathlib
import time
from typing import Callable, TYPE_CHECKING, cast
import uuid

from ..log import RuyiLogger
from ..utils.node_info import NodeInfo, gather_node_info
from .scope import TelemetryScope
from .store import TelemetryStore

if TYPE_CHECKING:
    # for avoiding circular import
    from ..config import GlobalConfig

FALLBACK_PM_TELEMETRY_ENDPOINT = "https://api.ruyisdk.cn/telemetry/pm/"

TELEMETRY_CONSENT_AND_UPLOAD_DESC = """
RuyiSDK collects anonymized usage data locally to help us improve the product.

[green]By default, nothing leaves your machine[/], and you can also turn off usage data
collection completely. Only with your explicit permission can [yellow]ruyi[/] upload
collected telemetry, periodically to RuyiSDK team-managed servers located in
the Chinese mainland. You can change this setting at any time by running
[yellow]ruyi telemetry consent[/], [yellow]ruyi telemetry local[/], or [yellow]ruyi telemetry optout[/].

If you enable uploads now, we'll also send a one-time report from this [yellow]ruyi[/]
installation so the RuyiSDK team can better understand adoption. Thank you for
helping us build a better experience!
"""
TELEMETRY_CONSENT_AND_UPLOAD_PROMPT = (
    "Enable telemetry uploads and send a one-time report now?"
)
TELEMETRY_OPTOUT_PROMPT = "\nDo you want to disable telemetry entirely?"


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


def set_telemetry_mode(
    gc: "GlobalConfig",
    mode: str,
    consent_time: datetime.datetime | None = None,
    show_cli_feedback: bool = True,
) -> None:
    """Set telemetry mode and consent time (if applicable) in the user preference."""

    from ..config.editor import ConfigEditor
    from ..config import schema

    logger = gc.logger

    if mode == "on":
        if consent_time is None:
            consent_time = datetime.datetime.now().astimezone()
    else:
        # clear any previously recorded consent time
        consent_time = None

    # First, persist the changes to user config
    with ConfigEditor.work_on_user_local_config(gc) as ed:
        ed.set_value((schema.SECTION_TELEMETRY, schema.KEY_TELEMETRY_MODE), mode)
        if consent_time is not None:
            ed.set_value(
                (schema.SECTION_TELEMETRY, schema.KEY_TELEMETRY_UPLOAD_CONSENT),
                consent_time,
            )
        else:
            ed.unset_value(
                (schema.SECTION_TELEMETRY, schema.KEY_TELEMETRY_UPLOAD_CONSENT)
            )

        ed.stage()

    # Then, apply the changes to the running instance's GlobalConfig
    # TelemetryProvider instance (if any) will pick them up automatically
    # because the properties are backed by GlobalConfig.
    gc.set_by_key(
        (schema.SECTION_TELEMETRY, schema.KEY_TELEMETRY_MODE),
        mode,
    )
    gc.set_by_key(
        (schema.SECTION_TELEMETRY, schema.KEY_TELEMETRY_UPLOAD_CONSENT),
        consent_time,
    )

    if not show_cli_feedback:
        return
    match mode:
        case "on":
            logger.I("telemetry data uploading is now enabled")
            logger.I(
                "you can opt out at any time by running [yellow]ruyi telemetry optout[/]"
            )
        case "local":
            logger.I("telemetry mode is now set to local collection only")
            logger.I(
                "you can re-enable telemetry data uploading at any time by running [yellow]ruyi telemetry consent[/]"
            )
            logger.I(
                "or opt out at any time by running [yellow]ruyi telemetry optout[/]"
            )
        case "off":
            logger.I("telemetry data collection is now disabled")
            logger.I(
                "you can re-enable telemetry data uploads at any time by running [yellow]ruyi telemetry consent[/]"
            )
        case _:
            raise ValueError(f"invalid telemetry mode: {mode}")


class TelemetryProvider:
    def __init__(self, gc: "GlobalConfig") -> None:
        self.state_root = pathlib.Path(gc.telemetry_root)

        self._discard_events = False
        self._gc = gc
        self._is_first_run = False
        self._stores: dict[TelemetryScope, TelemetryStore] = {}
        self._upload_on_exit = False

        # create the PM store
        self.init_store(TelemetryScope(None))
        # TODO: add real multi-repo support
        self.init_store(TelemetryScope("ruyisdk"))

    @property
    def logger(self) -> RuyiLogger:
        return self._gc.logger

    @property
    def local_mode(self) -> bool:
        return self._gc.telemetry_mode == "local"

    @property
    def upload_consent_time(self) -> datetime.datetime | None:
        return self._gc.telemetry_upload_consent_time

    def store(self, scope: TelemetryScope) -> TelemetryStore | None:
        return self._stores.get(scope)

    def init_store(self, scope: TelemetryScope) -> None:
        store_root = self.state_root
        api_url_fn: Callable[[], str | None] | None = None
        if repo_name := scope.repo_name:
            if repo_name != "ruyisdk":
                raise NotImplementedError("multi-repo support not implemented yet")
            store_root = store_root / "repos" / repo_name

            def _f() -> str | None:
                # access the repo attribute lazily to speed up CLI startup
                return self._gc.repo.get_telemetry_api_url("repo")

            api_url_fn = _f
        else:
            # configure the PM telemetry endpoint
            api_url_fn = functools.partial(self._detect_pm_api_url, self._gc)

        store = TelemetryStore(
            self.logger,
            scope,
            store_root,
            api_url_factory=api_url_fn,
        )
        self._stores[scope] = store

    def _detect_pm_api_url(self, gc: "GlobalConfig") -> str | None:
        url = FALLBACK_PM_TELEMETRY_ENDPOINT
        cfg_src = "fallback"
        if gc.override_pm_telemetry_url is not None:
            cfg_src = "local config"
            url = gc.override_pm_telemetry_url
        else:
            if repo_provided_url := gc.repo.get_telemetry_api_url("pm"):
                cfg_src = "repo"
                url = repo_provided_url
        self.logger.D(
            f"configured PM telemetry endpoint via {cfg_src}: {url or '(n/a)'}"
        )
        return url

    @property
    def installation_file(self) -> pathlib.Path:
        return self.state_root / "installation.json"

    def check_first_run_status(self) -> None:
        """Check if this is the first run of the application by checking if installation file exists.
        This must be done before init_installation() is potentially called.
        """
        self._is_first_run = not self.installation_file.exists()

    @property
    def is_first_run(self) -> bool:
        """Check if this is the first run of the application."""
        return self._is_first_run

    def init_installation(self, force_reinit: bool) -> NodeInfo | None:
        installation_file = self.installation_file
        if installation_file.exists() and not force_reinit:
            return self.read_installation_data()

        # either this is a fresh installation or we're forcing a refresh
        installation_id = uuid.uuid4()
        self.logger.D(
            f"initializing telemetry data store, installation_id={installation_id.hex}"
        )
        self.state_root.mkdir(parents=True, exist_ok=True)

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
                self.logger.I(
                    "telemetry mode is [green]local[/]: local data collection only, no uploads"
                )
            return

        now = time.time()
        if self.has_upload_consent(now) and not for_cli_verbose_output:
            self.logger.D("user has consented to telemetry upload")
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
        if for_cli_verbose_output:
            self.logger.I(
                "telemetry mode is [green]on[/]: data is collected and periodically uploaded"
            )
            self.logger.I(
                f"non-tracking usage information will be uploaded to RuyiSDK-managed servers [bold green]every {upload_wday_name}[/]"
            )
        else:
            self.logger.W(
                f"this [yellow]ruyi[/] installation has telemetry mode set to [yellow]on[/], and [bold]will upload non-tracking usage information to RuyiSDK-managed servers[/] [bold green]every {upload_wday_name}[/]"
            )

        if today_is_upload_day:
            for scope, store in self._stores.items():
                has_uploaded_today = self.has_uploaded_today(scope, now)
                if has_uploaded_today:
                    if last_upload_time := store.last_upload_timestamp:
                        last_upload_time_str = time.strftime(
                            "%Y-%m-%d %H:%M:%S %z", time.localtime(last_upload_time)
                        )
                        self.logger.I(
                            f"scope {scope}: usage information has already been uploaded today at {last_upload_time_str}"
                        )
                    else:
                        self.logger.I(
                            f"scope {scope}: usage information has already been uploaded sometime today"
                        )
                else:
                    self.logger.I(
                        f"scope {scope}: the next upload will happen [bold green]today[/] if not already"
                    )
        else:
            self.logger.I(
                f"the next upload will happen anytime [yellow]ruyi[/] is executed between [bold green]{next_upload_day_str}[/] and [bold green]{next_upload_day_end_str}[/]"
            )

        if not for_cli_verbose_output:
            self.logger.I("in order to hide this banner:")
            self.logger.I("- opt out with [yellow]ruyi telemetry optout[/]")
            self.logger.I("- or give consent with [yellow]ruyi telemetry consent[/]")

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

    def has_uploaded_today(
        self,
        scope: TelemetryScope,
        time_now: float | None = None,
    ) -> bool:
        if time_now is None:
            time_now = time.time()
        if upload_day := self.next_upload_day(time_now):
            upload_day_end = upload_day + 86400
            store = self.store(scope)
            if store is None:
                return False
            if last_upload_time := store.last_upload_timestamp:
                return upload_day <= last_upload_time < upload_day_end
        return False

    def record(self, scope: TelemetryScope, kind: str, **params: object) -> None:
        if store := self.store(scope):
            return store.record(kind, **params)
        self.logger.D(f"no telemetry store for scope {scope}, discarding event")

    def discard_events(self, v: bool = True) -> None:
        self._discard_events = v

    def flush(self, *, upload_now: bool = False) -> None:
        now = time.time()

        # We may be self-uninstalling and purging all state data, and in this
        # case we don't want to record anything (thus re-creating directories).
        if self._discard_events:
            self.logger.D("discarding collected telemetry data")
            return

        self.logger.D("flushing telemetry to persistent store")

        for scope, store in self._stores.items():
            store.persist(now)

            # try to upload if forced (upload_now or _upload_on_exit), or:
            #
            # * we're not in local mode
            # * today is the day
            # * we haven't uploaded today
            if not (upload_now or self._upload_on_exit) and (
                self.local_mode
                or not self.is_upload_day(now)
                or self.has_uploaded_today(scope, now)
            ):
                continue

            self.prepare_data_for_upload(store)
            self.upload_staged_payloads(store)

    def prepare_data_for_upload(self, store: TelemetryStore) -> None:
        installation_data: NodeInfo | None = None
        if store.scope.is_pm:
            try:
                installation_data = self.read_installation_data()
            except FileNotFoundError:
                # should not happen due to is_upload_day() initializing it for us
                # beforehand, but proceed without node info nonetheless
                pass

        return store.prepare_data_for_upload(installation_data)

    def upload_staged_payloads(self, store: TelemetryStore) -> None:
        if self.local_mode:
            return

        return store.upload_staged_payloads()

    def oobe_prompt(self) -> None:
        """Ask whether the user consents to a first-run telemetry upload, and
        persist the user's exact telemetry choice."""

        from ..cli import user_input

        self.logger.stdout(TELEMETRY_CONSENT_AND_UPLOAD_DESC)
        if not user_input.ask_for_yesno_confirmation(
            self.logger,
            TELEMETRY_CONSENT_AND_UPLOAD_PROMPT,
            False,
        ):
            # ask if the user wants to opt out entirely
            if user_input.ask_for_yesno_confirmation(
                self.logger,
                TELEMETRY_OPTOUT_PROMPT,
                False,
            ):
                set_telemetry_mode(self._gc, "off")
                return

            # user wants to stay in local mode
            # explicitly record the preference, so we don't have to worry about
            # us potentially changing defaults yet another time
            set_telemetry_mode(self._gc, "local")
            return

        consent_time = datetime.datetime.now().astimezone()
        set_telemetry_mode(self._gc, "on", consent_time)
        self._upload_on_exit = True
