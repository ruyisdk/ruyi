from contextlib import AbstractContextManager
from typing import Any, Self

from pygit2 import Oid
from pygit2.callbacks import RemoteCallbacks
from pygit2.enums import MergeAnalysis
from pygit2.remotes import TransferProgress
from pygit2.repository import Repository
from rich.progress import Progress, TaskID
from rich.text import Text

from .. import log


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

    def __enter__(self) -> Self:
        self.p.__enter__()
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, tb: Any) -> None:
        return self.p.__exit__(exc_type, exc_value, tb)

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
    repo: Repository,
    remote_name: str,
    remote_url: str,
    branch_name: str,
) -> None:
    remote = repo.remotes[remote_name]
    if remote.url != remote_url:
        log.D(f"updating url of remote {remote_name} from {remote.url} to {remote_url}")
        repo.remotes.set_url("origin", remote_url)

    log.D("fetching")
    with RemoteGitProgressIndicator() as pr:
        remote.fetch(callbacks=pr)

    remote_head_ref = repo.lookup_reference(f"refs/remotes/{remote_name}/{branch_name}")
    remote_head: Oid
    if isinstance(remote_head_ref.target, Oid):
        remote_head = remote_head_ref.target
    else:
        assert isinstance(remote_head_ref.target, str)
        remote_head = Oid(hex=remote_head_ref.target)

    merge_analysis, _ = repo.merge_analysis(remote_head)
    match merge_analysis:
        case MergeAnalysis.UP_TO_DATE:
            # nothing to do
            log.D("repo state already up-to-date")
            return
        case MergeAnalysis.UNBORN | MergeAnalysis.FASTFORWARD:
            # simple fast-forwarding is enough in both cases
            log.D(f"fast-forwarding repo to {remote_head.hex}")
            tgt = repo.get(remote_head)
            assert tgt is not None
            repo.checkout_tree(tgt)

            log.D(f"updating branch {branch_name} HEAD")
            local_branch_ref = repo.lookup_reference(f"refs/heads/{branch_name}")
            local_branch_ref.set_target(remote_head)
            repo.head.set_target(remote_head)
        case MergeAnalysis.NONE | MergeAnalysis.NORMAL:
            # cannot handle these cases
            log.F("cannot fast-forward repo to newly fetched state")
            log.I("manual intervention is required to avoid data loss")
            raise SystemExit(1)
