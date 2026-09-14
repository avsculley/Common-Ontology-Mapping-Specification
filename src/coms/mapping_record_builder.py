"""Build project-neutral governed mapping records from resolved source input."""

from __future__ import annotations

from .mapping_parser import (
    ENTITY_CLASS,
    ENTITY_OBJECT_PROPERTY,
    EntityResolver,
    parse_class_expression,
    parse_property_chain,
)
from .mapping_predicates import (
    OWL_EQUIVALENT_CLASS,
    OWL_EQUIVALENT_PROPERTY,
    OWL_PROPERTY_CHAIN_AXIOM,
    RDFS_DOMAIN,
    RDFS_RANGE,
    RDFS_SUBCLASS_OF,
    RDFS_SUBPROPERTY_OF,
)
from .mapping_record import (
    GovernedMappingRecord,
)


class MappingRecordBuildError(ValueError):
    """Resolved source input is incompatible with supported mapping semantics."""


def _require_subject_kind(
    subject_kind: str,
    expected_kind: str,
    predicate_iri: str,
) -> None:
    if subject_kind != expected_kind:
        raise MappingRecordBuildError(
            f"predicate {predicate_iri!r} requires "
            f"subject kind {expected_kind!r}, "
            f"found {subject_kind!r}"
        )


def build_governed_mapping_record(
    *,
    row_id: str,
    subject_iri: str,
    subject_kind: str,
    predicate_iri: str | None,
    target_text: str,
    resolver: EntityResolver,
    reasoning: str = "",
) -> GovernedMappingRecord:
    """Build one record using only currently supported COMS mapping predicates."""

    target = target_text.strip()

    if predicate_iri is None:
        if target:
            raise MappingRecordBuildError(
                "explicit blank mapping cannot contain target text"
            )

        return GovernedMappingRecord(
            row_id=row_id,
            subject_iri=subject_iri,
            predicate_iri=None,
            mapping_type="explicit_blank",
            reasoning=reasoning,
        )

    supported_predicates = {
        RDFS_SUBCLASS_OF,
        OWL_EQUIVALENT_CLASS,
        RDFS_SUBPROPERTY_OF,
        OWL_EQUIVALENT_PROPERTY,
        OWL_PROPERTY_CHAIN_AXIOM,
        RDFS_DOMAIN,
        RDFS_RANGE,
    }

    if predicate_iri not in supported_predicates:
        raise MappingRecordBuildError(
            f"unsupported mapping predicate {predicate_iri!r}"
        )

    if not target:
        raise MappingRecordBuildError(
            "active mapping requires target text"
        )

    if predicate_iri in {
        RDFS_SUBCLASS_OF,
        OWL_EQUIVALENT_CLASS,
    }:
        _require_subject_kind(
            subject_kind,
            ENTITY_CLASS,
            predicate_iri,
        )
        return GovernedMappingRecord(
            row_id=row_id,
            subject_iri=subject_iri,
            predicate_iri=predicate_iri,
            mapping_type="class_mapping",
            reasoning=reasoning,
            expression=parse_class_expression(
                target,
                resolver,
            ),
        )

    if predicate_iri in {
        RDFS_SUBPROPERTY_OF,
        OWL_EQUIVALENT_PROPERTY,
    }:
        _require_subject_kind(
            subject_kind,
            ENTITY_OBJECT_PROPERTY,
            predicate_iri,
        )
        return GovernedMappingRecord(
            row_id=row_id,
            subject_iri=subject_iri,
            predicate_iri=predicate_iri,
            mapping_type="object_property_mapping",
            reasoning=reasoning,
            target_property_iri=resolver.resolve_entity(
                target,
                ENTITY_OBJECT_PROPERTY,
            ),
        )

    if predicate_iri == OWL_PROPERTY_CHAIN_AXIOM:
        _require_subject_kind(
            subject_kind,
            ENTITY_OBJECT_PROPERTY,
            predicate_iri,
        )
        return GovernedMappingRecord(
            row_id=row_id,
            subject_iri=subject_iri,
            predicate_iri=predicate_iri,
            mapping_type="property_chain",
            reasoning=reasoning,
            property_chain=parse_property_chain(
                target,
                resolver,
            ),
        )

    _require_subject_kind(
        subject_kind,
        ENTITY_OBJECT_PROPERTY,
        predicate_iri,
    )
    return GovernedMappingRecord(
        row_id=row_id,
        subject_iri=subject_iri,
        predicate_iri=predicate_iri,
        mapping_type=(
            "domain"
            if predicate_iri == RDFS_DOMAIN
            else "range"
        ),
        reasoning=reasoning,
        expression=parse_class_expression(
            target,
            resolver,
        ),
    )
