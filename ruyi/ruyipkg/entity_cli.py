import argparse

from ..cli.cmd import RootCommand
from ..config import GlobalConfig


class EntityCommand(
    RootCommand,
    cmd="entity",
    has_subcommands=True,
    is_experimental=True,
    help="Interact with entities defined in the repositories",
):
    pass


class EntityDescribeCommand(
    EntityCommand,
    cmd="describe",
    help="Describe an entity",
):
    @classmethod
    def configure_args(cls, gc: GlobalConfig, p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "ref",
            help="Reference to the entity to describe in the form of '<type>:<name>'",
        )

    @classmethod
    def main(cls, cfg: GlobalConfig, args: argparse.Namespace) -> int:
        logger = cfg.logger
        ref = args.ref

        entity_store = cfg.repo.entity_store
        entity = entity_store.get_entity_by_ref(ref)
        if entity is None:
            logger.F(f"entity [yellow]{ref}[/] not found")
            return 1

        logger.stdout(
            f"Entity [bold]{str(entity)}[/] ([green]{entity.display_name}[/])\n"
        )

        fwd_refs = entity.related_refs
        if fwd_refs:
            logger.stdout("  Direct forward relationships:")
            for ref in sorted(fwd_refs):
                logger.stdout(f"    - [yellow]{ref}[/]")
        else:
            logger.stdout("  Direct forward relationships: [gray]none[/]")

        rev_refs = entity.reverse_refs
        if rev_refs:
            logger.stdout("  Direct reverse relationships:")
            for ref in sorted(rev_refs):
                logger.stdout(f"    - [yellow]{ref}[/]")
        else:
            logger.stdout("  Direct reverse relationships: [gray]none[/]")

        logger.stdout("  All indirectly related entities:")
        for e in entity_store.traverse_related_entities(
            entity,
            transitive=True,
            no_direct_refs=True,
            forward_refs=True,
            reverse_refs=True,
        ):
            logger.stdout(f"    - [yellow]{e}[/]")

        # TODO: render type-specific data

        return 0


class EntityListCommand(
    EntityCommand,
    cmd="list",
    help="List entities",
):
    @classmethod
    def configure_args(cls, gc: GlobalConfig, p: argparse.ArgumentParser) -> None:
        pass

    @classmethod
    def main(cls, cfg: GlobalConfig, args: argparse.Namespace) -> int:
        logger = cfg.logger
        entity_store = cfg.repo.entity_store
        for e in entity_store.iter_entities(None):
            logger.stdout(f"'{str(e)}':")
            logger.stdout(f"  display name: {e.display_name}")
            logger.stdout(f"  data: {e.data}")
            logger.stdout(f"  forward_refs: {e.related_refs}")
            logger.stdout(f"  reverse_refs: {e.reverse_refs}")
        return 0
