#!/usr/bin/env python3

import os
import pathlib
import re
import subprocess
import sys
from typing import NamedTuple, TypedDict, cast

import requests
from rich.console import Console
from rich import progress
import semver

GITHUB_BASE_URL = "https://api.github.com"
GITHUB_OWNER_REPO = "ruyisdk/ruyi"
MIME_GITHUB_JSON = "application/vnd.github+json"
MIME_OCTET_STREAM = "application/octet-stream"

ENV_RSYNC_STAGING_DIR = "RUYI_RELEASE_WORKER_RSYNC_STAGING_DIR"
ENV_RSYNC_REMOTE_URL = "RUYI_RELEASE_WORKER_RSYNC_REMOTE_URL"
ENV_RSYNC_REMOTE_PASS = "RUYI_RELEASE_WORKER_RSYNC_REMOTE_PASS"

USAGE = f"""\
usage: {{program_name}}

Environment variables:

* {ENV_RSYNC_STAGING_DIR}: Path to local state store and staging directory for rsync
* {ENV_RSYNC_REMOTE_URL}: URL to remote rsync server's ruyi release directory
* {ENV_RSYNC_REMOTE_PASS}: Password for rsync authentication if necessary
"""

RE_RUYI_RELEASE_ASSET_NAME = re.compile(
    r"^ruyi-(?P<ver>[0-9a-z.-]+)\.(?P<platform>[0-9a-z-]+)(?P<exe_suffix>\.exe)?$"
)

LOG = Console(stderr=True, highlight=False)
is_debug = False
program_name = __file__


def debug(*args: object) -> None:
    if not is_debug:
        return
    return LOG.log(*args)


def usage() -> None:
    LOG.print(USAGE.format(program_name=program_name))


def getenv_or_die(key: str) -> str:
    try:
        return os.environ[key]
    except KeyError:
        LOG.print(
            f"[bold red]fatal error[/]: environment variable '[yellow]{key}[/]' absent"
        )
        usage()
        sys.exit(1)


def github_get(
    url: str,
    accept: str,
    stream: bool = False,
    **kwargs: str | int,
) -> requests.Response:
    return requests.get(
        url,
        params=kwargs,
        stream=stream,
        headers={
            "Accept": accept,
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )


class GitHubReleaseAsset(TypedDict):
    url: str
    name: str
    size: int


class GitHubRelease(TypedDict):
    tag_name: str
    prerelease: bool
    assets: list[GitHubReleaseAsset]


def list_releases(owner_repo: str) -> list[GitHubRelease]:
    obj = github_get(
        f"{GITHUB_BASE_URL}/repos/{owner_repo}/releases",
        MIME_GITHUB_JSON,
        per_page=3,
    ).json()
    return cast(list[GitHubRelease], obj)


class Release(NamedTuple):
    kind: str
    name: str


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        usage()
        return 1

    rsync_staging_dir = getenv_or_die(ENV_RSYNC_STAGING_DIR)
    rsync_url = getenv_or_die(ENV_RSYNC_REMOTE_URL)
    rsync_pass = os.environ.get(ENV_RSYNC_REMOTE_PASS, None)

    if rsync_url.endswith("/"):
        LOG.print("[bold red]fatal error[/]: the rsync URL must not end with a slash")
        return 1

    remote = Rsync(rsync_url, rsync_pass)
    state_store = RsyncStagingDir(rsync_staging_dir)
    LOG.log(f"rsync staging directory at [cyan]{state_store.local_dir}")

    for gh_rel in list_releases(GITHUB_OWNER_REPO):
        name = gh_rel["tag_name"]
        kind = "testing" if gh_rel["prerelease"] else "releases"
        rel = Release(kind, name)

        # skip previous releases that were manually managed
        if semver.compare(name, "0.6.0") <= 0:
            debug(f"{name}: ignoring pre-automation releases")
            continue

        is_synced = state_store.is_release_synced(rel)
        synced_str = "[green]synced[/]" if is_synced else "[yellow]needs sync[/]"
        LOG.log(f"{name}: [cyan]{kind}[/] {synced_str}")
        if is_synced:
            continue

        rel_dir = state_store.get_local_release_dir(rel)
        rel_dir.mkdir(parents=True, exist_ok=True)
        LOG.log(f"{name}: pulling assets")
        ensure_release_assets(rel_dir, gh_rel["assets"])

        LOG.log(f"{name}: pushing to remote")
        remote.sync(rel, rel_dir)
        state_store.mark_release_synced(rel)

    return 0


def transform_asset_name(gh_artifact_name: str) -> str:
    m = RE_RUYI_RELEASE_ASSET_NAME.match(gh_artifact_name)
    if m is None:
        return gh_artifact_name

    platform = m["platform"]
    exe_suffix = m["exe_suffix"] or ""
    return f"ruyi.{platform}{exe_suffix}"


def ensure_release_assets(
    local_dir: pathlib.Path,
    assets: list[GitHubReleaseAsset],
) -> None:
    for asset in assets:
        local_file = local_dir / transform_asset_name(asset["name"])
        debug(f"asset [green]{asset['name']}[/]: local [cyan]{local_file}")
        try:
            if local_file.stat().st_size == asset["size"]:
                debug(f"asset [green]{asset['name']}[/]: size matches")
                continue
        except FileNotFoundError:
            pass
        LOG.log(f"removing [cyan]{local_file}")
        local_file.unlink(missing_ok=True)
        download_gh_release_asset_to(asset, local_file)
        local_file.chmod(0o755)


def download_gh_release_asset_to(
    asset: GitHubReleaseAsset,
    local: pathlib.Path,
) -> None:
    r = github_get(asset["url"], MIME_OCTET_STREAM, stream=True)
    chunk_size = 16 * 1024
    LOG.log(f"downloading [cyan]{asset['url']}[/] to [cyan]{local}")
    columns = (
        progress.SpinnerColumn(),
        progress.BarColumn(),
        progress.DownloadColumn(),
        progress.TransferSpeedColumn(),
        progress.TimeRemainingColumn(compact=True, elapsed_when_finished=True),
    )
    with open(local, "wb") as f:
        with progress.Progress(*columns, console=LOG) as pg:
            task = pg.add_task(asset["name"], total=asset["size"])
            for chunk in r.iter_content(chunk_size):
                f.write(chunk)
                pg.advance(task, len(chunk))


class Rsync:
    def __init__(self, conn_url: str, password: str | None = None) -> None:
        self.conn_url = conn_url
        self.password = password

    def sync(self, rel: Release, local_dir: str | pathlib.Path) -> None:
        new_env: dict[bytes, bytes] | None = None
        if self.password is not None:
            new_env = os.environb.copy()
            new_env[b"RSYNC_PASSWORD"] = self.password.encode("utf-8")

        remote_spec = f"{self.conn_url}/{rel.kind}/{rel.name}/"
        local_spec = f"{local_dir}/"

        args = ("rsync", "-avHPL", "--exclude=.synced", local_spec, remote_spec)
        LOG.log(f"calling rsync with args: {args[1:]}")
        subprocess.run(args, check=True, env=new_env)


class RsyncStagingDir:
    def __init__(self, local_dir: str) -> None:
        self.local_dir = pathlib.Path(local_dir)

    def get_local_release_dir(self, rel: Release) -> pathlib.Path:
        return self.local_dir / rel.kind / rel.name

    def get_marker_path_for_release(self, rel: Release, marker: str) -> pathlib.Path:
        return self.get_local_release_dir(rel) / f".{marker}"

    def is_release_synced(self, rel: Release) -> bool:
        return self.get_marker_path_for_release(rel, "synced").exists()

    def mark_release_synced(self, rel: Release) -> None:
        self.get_marker_path_for_release(rel, "synced").touch()


if __name__ == "__main__":
    program_name = sys.argv[0]
    # same as ruyi.cli.init_debug_status
    debug_env = os.environ.get("RUYI_DEBUG", "")
    is_debug = debug_env.lower() in {"1", "true", "x", "y", "yes"}

    sys.exit(main(sys.argv))
