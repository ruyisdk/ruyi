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


class EntityDescribeCommand(
    EntityCommand,
    cmd="describe",
    help="Describe an entity",
):
    @classmethod
    def configure_args(cls, p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "ref",
            help="Reference to the entity to describe in the form of '<type>:<name>'",
        )

    @classmethod
    def main(cls, cfg: GlobalConfig, args: argparse.Namespace) -> int:
        ref = args.ref

        entity_store = cfg.repo.entity_store
        entity = entity_store.get_entity_by_ref(ref)
        if entity is None:
            log.F(f"entity [yellow]{ref}[/] not found")
            return 1

        log.stdout(f"Entity [bold]{str(entity)}[/] ([green]{entity.display_name}[/])\n")

        fwd_refs = entity.related_refs
        if fwd_refs:
            log.stdout("  Direct forward relationships:")
            for ref in sorted(fwd_refs):
                log.stdout(f"    - [yellow]{ref}[/]")
        else:
            log.stdout("  Direct forward relationships: [gray]none[/]")

        rev_refs = entity.reverse_refs
        if rev_refs:
            log.stdout("  Direct reverse relationships:")
            for ref in sorted(rev_refs):
                log.stdout(f"    - [yellow]{ref}[/]")
        else:
            log.stdout("  Direct reverse relationships: [gray]none[/]")

        # TODO: render type-specific data and transitive relationships

        return 0


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
