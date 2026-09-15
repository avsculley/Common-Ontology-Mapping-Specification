"""Wire unresolved workbook rows into existing COMS mapping semantics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .adapters.xlsx import WorkbookSourceRow
from .mapping_parser import (
    ENTITY_CLASS,
    ENTITY_OBJECT_PROPERTY,
    EntityResolver,
)
from .mapping_predicates import (
    normalize_mapping_predicate_token,
)
from .mapping_record import GovernedMappingRecord
from .mapping_record_builder import (
    build_governed_mapping_record,
)


@dataclass(frozen=True)
class ResolvedSourceEntity:
    """One project-resolved source IRI and its supported entity kind."""

    iri: str
    kind: str


class SourceEntityResolver(Protocol):
    """Resolve a source token and discover its supported entity kind."""

    def resolve_source_entity(
        self,
        token: str,
    ) -> ResolvedSourceEntity:
        """Resolve one source token according to project-supplied policy."""
        ...


class WorkbookMappingError(ValueError):
    """An unresolved workbook row cannot enter generic mapping semantics."""


def build_governed_mapping_record_from_workbook_row(
    row: WorkbookSourceRow,
    source_resolver: SourceEntityResolver,
    target_resolver: EntityResolver,
) -> GovernedMappingRecord:
    """Resolve and build one workbook row through existing COMS authorities."""

    subject_token = row.subject_text.strip()

    if not subject_token:
        raise WorkbookMappingError(
            "workbook mapping row requires nonblank subject text"
        )

    subject = source_resolver.resolve_source_entity(
        subject_token
    )

    if subject.kind not in {
        ENTITY_CLASS,
        ENTITY_OBJECT_PROPERTY,
    }:
        raise WorkbookMappingError(
            "source resolver returned unsupported entity kind "
            f"{subject.kind!r}"
        )

    return build_governed_mapping_record(
        row_id=row.row_id_text,
        subject_iri=subject.iri,
        subject_kind=subject.kind,
        predicate_iri=normalize_mapping_predicate_token(
            row.predicate_text
        ),
        target_text=row.target_text,
        resolver=target_resolver,
        reasoning=row.reasoning_text,
    )
