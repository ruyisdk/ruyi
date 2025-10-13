from contextlib import AbstractContextManager
import pathlib
from typing import Any, TYPE_CHECKING

from pygit2 import GitError, Oid
from pygit2.callbacks import RemoteCallbacks
from pygit2.repository import Repository

try:
    from pygit2.remotes import TransferProgress
except ModuleNotFoundError:
    # pygit2 < 1.14.0
    # see https://github.com/libgit2/pygit2/commit/a8b2421bea550292
    #
    # import-untyped: the current pygit2 type stubs were written after the
    # `remote` -> `remotes` rename, so no stubs for it
    from pygit2.remote import TransferProgress  # type: ignore[import-not-found,import-untyped,no-redef,unused-ignore]

# for compatibility with <1.14.0, cannot `from pygit2.enums import MergeAnalysis`
# see https://github.com/libgit2/pygit2/pull/1251
from pygit2 import (
    GIT_MERGE_ANALYSIS_UNBORN,
    GIT_MERGE_ANALYSIS_FASTFORWARD,
    GIT_MERGE_ANALYSIS_UP_TO_DATE,
)

from rich.progress import Progress, TaskID
from rich.text import Text

if TYPE_CHECKING:
    from typing_extensions import Self

from ..log import RuyiLogger


def human_readable_path_of_repo(repo: Repository) -> pathlib.Path:
    """
    Returns a human-readable path of the repository.
    If the repository is a submodule, returns the path to the parent module.
    """
    repo_path = pathlib.Path(repo.path)
    return repo_path.parent if repo_path.name == ".git" else repo_path


class RemoteGitProgressIndicator(
    RemoteCallbacks,
    AbstractContextManager["RemoteGitProgressIndicator"],
):
    def __init__(self) -> None:
        super().__init__()
        self.p = Progress()
        self.task: TaskID | None = None
        self._last_stats: TransferProgress | None = None
        self._task_name: str = ""

    def __enter__(self) -> "Self":
        self.p.__enter__()
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, tb: Any) -> None:
        return self.p.__exit__(exc_type, exc_value, tb)

    # Compatibility with pygit2 < 1.8.0.
    def progress(self, string: str) -> None:
        return self.sideband_progress(string)

    def sideband_progress(self, string: str) -> None:
        self.p.console.print("\r", Text(string), sep="", end="")

    def transfer_progress(self, stats: TransferProgress) -> None:
        new_phase = False
        task_name: str = self._task_name
        total: int = 0
        completed: int = 0

        if (
            self._last_stats is None
            or self._last_stats.received_objects != stats.received_objects
        ):
            task_name = "transferring objects"
            total = stats.total_objects
            completed = stats.received_objects
        elif self._last_stats.indexed_deltas != stats.indexed_deltas:
            task_name = "processing deltas"
            total = stats.total_deltas
            completed = stats.indexed_deltas
        elif self._last_stats.received_bytes != stats.received_bytes:
            # we don't render the received size at the moment
            pass

        new_phase = self._task_name != task_name
        if new_phase:
            self.task = self.p.add_task(task_name, total=total, completed=completed)
            self._task_name = task_name
        else:
            if self.task is not None:
                self.p.update(self.task, total=total, completed=completed)

        self._last_stats = stats


# based on https://stackoverflow.com/questions/27749418/implementing-pull-with-pygit2
def pull_ff_or_die(
    logger: RuyiLogger,
    repo: Repository,
    remote_name: str,
    remote_url: str,
    branch_name: str,
    *,
    allow_auto_management: bool,
) -> None:
    remote = repo.remotes[remote_name]
    if remote.url != remote_url:
        if not allow_auto_management:
            logger.F(
                f"URL of remote '[yellow]{remote_name}[/]' does not match expected URL"
            )
            repo_path = human_readable_path_of_repo(repo)
            logger.I(f"repository:          [yellow]{repo_path}[/]")
            logger.I(f"expected remote URL: [yellow]{remote_url}[/]")
            logger.I(f"actual remote URL:   [yellow]{remote.url}[/]")
            logger.I("please [bold red]fix the repo settings manually[/]")
            raise SystemExit(1)

        logger.D(
            f"updating url of remote {remote_name} from {remote.url} to {remote_url}"
        )
        repo.remotes.set_url(remote_name, remote_url)
        # this needs manual refreshing
        remote = repo.remotes[remote_name]

    logger.D("fetching")
    try:
        with RemoteGitProgressIndicator() as pr:
            remote.fetch(callbacks=pr)
    except GitError as e:
        logger.F(f"failed to fetch from remote URL {remote_url}: {e}")
        raise SystemExit(1) from e

    remote_head_ref = repo.lookup_reference(f"refs/remotes/{remote_name}/{branch_name}")
    remote_head: Oid
    if isinstance(remote_head_ref.target, Oid):
        remote_head = remote_head_ref.target
    else:
        assert isinstance(remote_head_ref.target, str)
        remote_head = Oid(hex=remote_head_ref.target)

    merge_analysis, _ = repo.merge_analysis(remote_head)

    if merge_analysis & GIT_MERGE_ANALYSIS_UP_TO_DATE:
        # nothing to do
        logger.D("repo state already up-to-date")
        return

    if merge_analysis & (GIT_MERGE_ANALYSIS_UNBORN | GIT_MERGE_ANALYSIS_FASTFORWARD):
        # simple fast-forwarding is enough in both cases
        logger.D(f"fast-forwarding repo to {remote_head}")
        tgt = repo.get(remote_head)
        assert tgt is not None
        repo.checkout_tree(tgt)

        logger.D(f"updating branch {branch_name} HEAD")
        local_branch_ref = repo.lookup_reference(f"refs/heads/{branch_name}")
        local_branch_ref.set_target(remote_head)
        repo.head.set_target(remote_head)
        return

    # cannot handle these cases
    logger.F("cannot fast-forward repo to newly fetched state")
    logger.I("manual intervention is required to avoid data loss")
    raise SystemExit(1)
