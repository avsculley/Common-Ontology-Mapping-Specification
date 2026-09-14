"""Compose deterministic COMS ontology documents from governed mappings."""

from __future__ import annotations

from collections.abc import Iterable

from .config.model import ProjectConfig
from .mapping_compiler import render_mapping_record_turtle
from .mapping_record import GovernedMappingRecord
from .publication import render_ontology_header_bytes
from .release_context import FormalReleaseContext


class OntologyDocumentError(ValueError):
    """A deterministic ontology document cannot be composed."""

    def __init__(
        self,
        duplicate_statement: bytes,
    ) -> None:
        self.duplicate_statement = duplicate_statement
        super().__init__(
            "duplicate active mapping statement: "
            f"{duplicate_statement!r}"
        )


def render_ontology_document(
    config: ProjectConfig,
    product_key: str,
    records: Iterable[GovernedMappingRecord],
    context: FormalReleaseContext | None = None,
) -> bytes:
    """Render a publication header and caller-selected mappings as Turtle."""

    header = render_ontology_header_bytes(
        config,
        product_key,
        context,
    )
    statements = sorted(
        statement
        for record in records
        if (
            statement
            := render_mapping_record_turtle(
                record
            )
        )
    )

    for previous, statement in zip(
        statements,
        statements[1:],
    ):
        if statement == previous:
            raise OntologyDocumentError(
                statement
            )

    return header + b"".join(
        statements
    )
