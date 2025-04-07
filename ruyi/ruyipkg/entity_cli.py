import argparse

from .. import log
from ..cli.cmd import RootCommand
from ..config import GlobalConfig


class EntityCommand(
    RootCommand,
    cmd="entity",
    has_subcommands=True,
    is_experimental=True,
    help="Interact with entities defined in the repositories",
):
    @classmethod
    def configure_args(cls, p: argparse.ArgumentParser) -> None:
        pass


class EntityListCommand(
    EntityCommand,
    cmd="list",
    help="List entities",
):
    @classmethod
    def configure_args(cls, p: argparse.ArgumentParser) -> None:
        pass

    @classmethod
    def main(cls, cfg: GlobalConfig, args: argparse.Namespace) -> int:
        entity_store = cfg.repo.entity_store
        for e in entity_store.iter_entities(None):
            log.stdout(f"'{str(e)}':")
            log.stdout(f"  display name: {e.display_name}")
            log.stdout(f"  data: {e.data}")
            log.stdout(f"  forward_refs: {e.related_refs}")
            log.stdout(f"  reverse_refs: {e.reverse_refs}")
        return 0
