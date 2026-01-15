import calendar
import datetime
import functools
import json
import pathlib
import time
from typing import Callable, TYPE_CHECKING, cast
import uuid

from ..i18n import _, d_
from ..log import RuyiLogger
from ..utils.node_info import NodeInfo, gather_node_info
from .scope import TelemetryScope
from .store import TelemetryStore

if TYPE_CHECKING:
    # for avoiding circular import
    from ..config import GlobalConfig

FALLBACK_PM_TELEMETRY_ENDPOINT = "https://api.ruyisdk.cn/telemetry/pm/"

TELEMETRY_CONSENT_AND_UPLOAD_DESC = d_(
    """
RuyiSDK collects minimal usage data in the form of just a version number of
the running [yellow]ruyi[/], to help us improve the product. With your consent,
RuyiSDK may also collect additional non-tracking usage data to be sent
periodically. The data will be recorded and processed by RuyiSDK team-managed
servers located in the Chinese mainland.

[green]By default, nothing leaves your machine[/], and you can also turn off usage data
collection completely. Only with your explicit permission can [yellow]ruyi[/] collect and
upload more usage data. You can change this setting at any time by running
[yellow]ruyi telemetry consent[/], [yellow]ruyi telemetry local[/], or [yellow]ruyi telemetry optout[/].

We'll also send a one-time report from this [yellow]ruyi[/] installation so the RuyiSDK
team can better understand adoption. If you choose to opt out, this will be the
only data to be ever uploaded, without any tracking ID being generated or kept.
Thank you for helping us build a better experience!
"""
)
TELEMETRY_CONSENT_AND_UPLOAD_PROMPT = d_(
    "Do you agree to have usage data periodically uploaded?"
)
TELEMETRY_OPTOUT_PROMPT = d_("\nDo you want to opt out of telemetry entirely?")
MALFORMED_TELEMETRY_STATE_MSG = d_(
    "malformed telemetry state: unable to determine upload weekday, nothing will be uploaded"
)


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
            logger.I(_("telemetry data uploading is now enabled"))
            logger.I(
                _(
                    "you can opt out at any time by running [yellow]ruyi telemetry optout[/]"
                )
            )
        case "local":
            logger.I(_("telemetry mode is now set to local collection only"))
            logger.I(
                _(
                    "you can re-enable telemetry data uploading at any time by running [yellow]ruyi telemetry consent[/]"
                )
            )
            logger.I(
                _("or opt out at any time by running [yellow]ruyi telemetry optout[/]")
            )
        case "off":
            logger.I(_("telemetry data collection is now disabled"))
            logger.I(
                _(
                    "you can re-enable telemetry data uploads at any time by running [yellow]ruyi telemetry consent[/]"
                )
            )
        case _:
            raise ValueError(f"invalid telemetry mode: {mode}")


class TelemetryProvider:
    def __init__(self, gc: "GlobalConfig", minimal: bool) -> None:
        self.state_root = pathlib.Path(gc.telemetry_root)

        self._discard_events = False
        self._gc = gc
        self._is_first_run = False
        self._stores: dict[TelemetryScope, TelemetryStore] = {}
        self._upload_on_exit = False
        self.minimal = minimal

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
        if self.minimal or self.local_mode:
            return None
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

    @property
    def minimal_installation_marker_file(self) -> pathlib.Path:
        return self.state_root / "minimal-installation-marker"

    def check_first_run_status(self) -> None:
        """Check if this is the first run of the application by checking if installation file exists.
        This must be done before init_installation() is potentially called.
        """
        self._is_first_run = (
            not self.installation_file.exists()
            and not self.minimal_installation_marker_file.exists()
        )

    @property
    def is_first_run(self) -> bool:
        """Check if this is the first run of the application."""
        return self._is_first_run

    def init_installation(self, force_reinit: bool) -> NodeInfo | None:
        if self.minimal:
            # be extra safe by not reading or writing installation data at all
            # in minimal mode
            self._init_minimal_installation_marker(force_reinit)
            return None

        installation_file = self.installation_file
        if installation_file.exists() and not force_reinit:
            return self._read_installation_data()

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

    def _init_minimal_installation_marker(self, force_reinit: bool) -> None:
        if self.minimal_installation_marker_file.exists() and not force_reinit:
            return

        self.logger.D("initializing minimal installation marker file")
        self.state_root.mkdir(parents=True, exist_ok=True)

        # just touch the file
        self.minimal_installation_marker_file.touch()

    def _read_installation_data(self) -> NodeInfo | None:
        with open(self.installation_file, "rb") as fp:
            return cast(NodeInfo, json.load(fp))

    def _upload_weekday(self) -> int | None:
        if self.minimal:
            return None

        try:
            installation_data = self._read_installation_data()
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

    def _has_upload_consent(self, time_now: float | None = None) -> bool:
        if self.upload_consent_time is None:
            return False
        if time_now is None:
            time_now = time.time()
        return self.upload_consent_time.timestamp() <= time_now

    def _print_upload_schedule_notice(self, upload_wday: int, now: float) -> None:
        next_upload_day_ts = next_utc_weekday(upload_wday, now)
        next_upload_day = time.localtime(next_upload_day_ts)
        next_upload_day_end = time.localtime(next_upload_day_ts + 86400)
        next_upload_day_str = time.strftime("%Y-%m-%d %H:%M:%S %z", next_upload_day)
        next_upload_day_end_str = time.strftime(
            "%Y-%m-%d %H:%M:%S %z",
            next_upload_day_end,
        )

        if self._is_upload_day(now):
            for scope, store in self._stores.items():
                has_uploaded_today = self._has_uploaded_today(
                    store.last_upload_timestamp,
                    now,
                )
                if has_uploaded_today:
                    if last_upload_time := store.last_upload_timestamp:
                        last_upload_time_str = time.strftime(
                            "%Y-%m-%d %H:%M:%S %z", time.localtime(last_upload_time)
                        )
                        self.logger.I(
                            _(
                                "scope {scope}: usage information has already been uploaded today at {last_upload_time_str}"
                            ).format(
                                scope=scope,
                                last_upload_time_str=last_upload_time_str,
                            )
                        )
                    else:
                        self.logger.I(
                            _(
                                "scope {scope}: usage information has already been uploaded sometime today"
                            ).format(
                                scope=scope,
                            )
                        )
                else:
                    self.logger.I(
                        _(
                            "scope {scope}: the next upload will happen [bold green]today[/] if not already"
                        ).format(
                            scope=scope,
                        )
                    )
        else:
            self.logger.I(
                _("the next upload will happen anytime [yellow]ruyi[/] is executed:")
            )
            self.logger.I(
                _(
                    "  -  between [bold green]{time_start}[/] and [bold green]{time_end}[/]"
                ).format(
                    time_start=next_upload_day_str,
                    time_end=next_upload_day_end_str,
                )
            )
            self.logger.I(_("  - or if the last upload is more than a week ago"))

    def print_telemetry_notice(self, for_cli_verbose_output: bool = False) -> None:
        if self.minimal:
            if for_cli_verbose_output:
                self.logger.I(
                    _(
                        "telemetry mode is [green]off[/]: nothing is collected or uploaded after the first run"
                    )
                )
            return

        now = time.time()
        upload_wday = self._upload_weekday()
        if upload_wday is None:
            if for_cli_verbose_output:
                self.logger.W(MALFORMED_TELEMETRY_STATE_MSG)
            else:
                self.logger.D(MALFORMED_TELEMETRY_STATE_MSG)
            return

        upload_wday_name = calendar.day_name[upload_wday]

        if self.local_mode:
            if for_cli_verbose_output:
                self.logger.I(
                    _(
                        "telemetry mode is [green]local[/]: local usage collection only, no usage uploads except if requested"
                    )
                )
            return

        if self._has_upload_consent(now) and not for_cli_verbose_output:
            self.logger.D("user has consented to telemetry upload")
            return

        if for_cli_verbose_output:
            self.logger.I(
                _(
                    "telemetry mode is [green]on[/]: usage data is collected and periodically uploaded"
                )
            )
            self.logger.I(
                _(
                    "non-tracking usage information will be uploaded to RuyiSDK-managed servers [bold green]every {weekday}[/]"
                ).format(
                    weekday=upload_wday_name,
                )
            )
        else:
            self.logger.W(
                _(
                    "this [yellow]ruyi[/] installation has telemetry mode set to [yellow]on[/], and [bold]will upload non-tracking usage information to RuyiSDK-managed servers[/] [bold green]every {weekday}[/]"
                ).format(
                    weekday=upload_wday_name,
                )
            )

        self._print_upload_schedule_notice(upload_wday, now)

        if not for_cli_verbose_output:
            self.logger.I(_("in order to hide this banner:"))
            self.logger.I(_(" - opt out with [yellow]ruyi telemetry optout[/]"))
            self.logger.I(
                _(" - or give consent with [yellow]ruyi telemetry consent[/]")
            )

    def _next_upload_day(self, time_now: float | None = None) -> int | None:
        upload_wday = self._upload_weekday()
        if upload_wday is None:
            return None
        return next_utc_weekday(upload_wday, time_now)

    def _is_upload_day(self, time_now: float | None = None) -> bool:
        if time_now is None:
            time_now = time.time()
        if upload_day := self._next_upload_day(time_now):
            return upload_day <= time_now
        return False

    def _has_uploaded_today(
        self,
        last_upload_time: float | None,
        time_now: float | None = None,
    ) -> bool:
        if time_now is None:
            time_now = time.time()
        if upload_day := self._next_upload_day(time_now):
            upload_day_end = upload_day + 86400
            if last_upload_time is not None:
                return upload_day <= last_upload_time < upload_day_end
        return False

    def record(self, scope: TelemetryScope, kind: str, **params: object) -> None:
        if self.minimal:
            self.logger.D(
                f"minimal telemetry mode enabled, discarding event '{kind}' for scope {scope}"
            )
            return

        if store := self.store(scope):
            return store.record(kind, **params)
        self.logger.D(
            f"no telemetry store for scope {scope}, discarding event '{kind}'"
        )

    def discard_events(self, v: bool = True) -> None:
        self._discard_events = v

    def _should_proceed_with_upload(
        self,
        scope: TelemetryScope,
        explicit_request: bool,
        cron_mode: bool,
        now: float,
    ) -> tuple[bool, str]:
        # proceed to uploading if forced (explicit requested or _upload_on_exit)
        # regardless of schedule
        if explicit_request:
            return True, "explicit request"
        if self._upload_on_exit:
            return True, "first-run upload on exit"

        # this is not an explicitly requested upload, so only proceed if today
        # is the day, or if the last upload is more than a week ago
        #
        # the last-upload-more-than-a-week-ago check is to avoid situations
        # where the user has not run ruyi for a long time, thus missing
        # the scheduled upload day.
        #
        # cron jobs are a mitigation, but we cannot rely on them either, because:
        #
        # * ruyi is more likely installed user-locally than system-wide, so
        #   users may not set up cron jobs for themselves;
        # * telemetry data is always recorded per user so system-wide cron jobs
        #   cannot easily access this data.
        last_upload_time: float | None = None
        if store := self.store(scope):
            last_upload_time = store.last_upload_timestamp

        if not self._is_upload_day(now):
            if last_upload_time is not None and now - last_upload_time >= 7 * 86400:
                return True, "last upload more than a week ago"
            return False, "not upload day"
        # now we're sure today is the day

        # if we're in cron mode, proceed as if it's an explicit request;
        # otherwise, only proceed if mode is "on" and we haven't uploaded yet today
        # for this scope
        if cron_mode:
            return True, "cron mode upload on upload day"

        if self._gc.telemetry_mode != "on":
            return False, "telemetry mode not 'on'"

        if not self._has_uploaded_today(last_upload_time, now):
            return True, "upload day, not yet uploaded today"
        return False, "upload day, already uploaded today"

    def flush(self, *, upload_now: bool = False, cron_mode: bool = False) -> None:
        """
        Flush collected telemetry data to persistent store, and upload if needed.

        :param upload_now: Upload data right now regardless of schedule.
        :type upload_now: bool
        :param cron_mode: Whether this flush is called from a cron job. If true,
            non-upload-day uploads will be skipped, otherwise acts just like
            explicit uploads via `ruyi telemetry upload`.
        :type cron_mode: bool
        """

        # We may be self-uninstalling and purging all state data, and in this
        # case we don't want to record anything (thus re-creating directories).
        if self._discard_events:
            self.logger.D("discarding collected telemetry data")
            return

        now = time.time()

        def should_proceed(scope: TelemetryScope) -> tuple[bool, str]:
            return self._should_proceed_with_upload(
                scope,
                explicit_request=upload_now,
                cron_mode=cron_mode,
                now=now,
            )

        if self.minimal:
            if not self._upload_on_exit:
                self.logger.D("skipping upload for non-first-run in minimal mode")
                return

            for scope, store in self._stores.items():
                go_ahead, reason = should_proceed(scope)
                self.logger.D(
                    f"minimal telemetry upload check for scope {scope}: go_ahead={go_ahead}, reason={reason}"
                )
                if not go_ahead:
                    continue
                store.upload_minimal()
            return

        for scope, store in self._stores.items():
            self.logger.D(f"flushing telemetry to persistent store for scope {scope}")
            store.persist(now)

            go_ahead, reason = should_proceed(scope)
            self.logger.D(
                f"regular telemetry upload check for scope {scope}: go_ahead={go_ahead}, reason={reason}"
            )
            if not go_ahead:
                continue

            self._prepare_data_for_upload(store)
            store.upload_staged_payloads()

    def _prepare_data_for_upload(self, store: TelemetryStore) -> None:
        installation_data: NodeInfo | None = None
        if store.scope.is_pm:
            try:
                installation_data = self._read_installation_data()
            except FileNotFoundError:
                # should not happen due to is_upload_day() initializing it for us
                # beforehand, but proceed without node info nonetheless
                pass

        return store.prepare_data_for_upload(installation_data)

    def oobe_prompt(self) -> None:
        """Ask whether the user consents to a first-run telemetry upload, and
        persist the user's exact telemetry choice."""

        if self._gc.is_telemetry_optout:
            # user has already explicitly opted out via the environment variable,
            # don't bother asking
            return

        # We always report installation info on first run, regardless of
        # user's telemetry choice. In case the user opts out, only do a one-time
        # upload now, and never upload anything again.
        self._upload_on_exit = True

        from ..cli import user_input

        self.logger.stdout(_(TELEMETRY_CONSENT_AND_UPLOAD_DESC))
        if not user_input.ask_for_yesno_confirmation(
            self.logger,
            _(TELEMETRY_CONSENT_AND_UPLOAD_PROMPT),
            False,
        ):
            # ask if the user wants to opt out entirely
            if user_input.ask_for_yesno_confirmation(
                self.logger,
                _(TELEMETRY_OPTOUT_PROMPT),
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
