import argparse
from typing import TYPE_CHECKING

from ..cli.cmd import RootCommand

if TYPE_CHECKING:
    from ..cli.completion import ArgumentParser
    from ..config import GlobalConfig


class EntityCommand(
    RootCommand,
    cmd="entity",
    has_subcommands=True,
    is_experimental=True,
    help="Interact with entities defined in the repositories",
):
    @classmethod
    def configure_args(cls, gc: "GlobalConfig", p: "ArgumentParser") -> None:
        pass


class EntityDescribeCommand(
    EntityCommand,
    cmd="describe",
    help="Describe an entity",
):
    @classmethod
    def configure_args(cls, gc: "GlobalConfig", p: "ArgumentParser") -> None:
        p.add_argument(
            "ref",
            help="Reference to the entity to describe in the form of '<type>:<name>'",
        )

    @classmethod
    def main(cls, cfg: "GlobalConfig", args: argparse.Namespace) -> int:
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
    def configure_args(cls, gc: "GlobalConfig", p: "ArgumentParser") -> None:
        p.add_argument(
            "-t",
            "--entity-type",
            action="append",
            nargs=1,
            dest="entity_type",
            help="List entities of this type. Can be passed multiple times to list multiple types.",
        )

    @classmethod
    def main(cls, cfg: "GlobalConfig", args: argparse.Namespace) -> int:
        from ..utils.porcelain import PorcelainOutput

        entity_types_in: list[list[str]] | None = args.entity_type
        entity_types: list[str] | None = None
        if entity_types_in is not None:
            entity_types = [x[0] for x in entity_types_in]

        logger = cfg.logger
        entity_store = cfg.repo.entity_store

        # Check if porcelain output is requested
        if cfg.is_porcelain:
            with PorcelainOutput() as po:
                for e in entity_store.iter_entities(entity_types):
                    po.emit(e.to_porcelain())
            return 0

        # Human-readable output
        for e in entity_store.iter_entities(entity_types):
            logger.stdout(f"'{str(e)}':")
            logger.stdout(f"  display name: {e.display_name}")
            logger.stdout(f"  data: {e.data}")
            logger.stdout(f"  forward_refs: {e.related_refs}")
            logger.stdout(f"  reverse_refs: {e.reverse_refs}")
        return 0
