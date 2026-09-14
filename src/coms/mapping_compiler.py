"""Compile governed COMS mapping records to deterministic RDF/Turtle bytes."""

from __future__ import annotations

from .mapping_expression import (
    ExpressionNode,
    MappingExpressionError,
    canonical_iri_term,
    canonicalize_expression,
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


_RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
_OWL_CLASS = "http://www.w3.org/2002/07/owl#Class"
_OWL_RESTRICTION = "http://www.w3.org/2002/07/owl#Restriction"
_OWL_INTERSECTION_OF = "http://www.w3.org/2002/07/owl#intersectionOf"
_OWL_UNION_OF = "http://www.w3.org/2002/07/owl#unionOf"
_OWL_ON_PROPERTY = "http://www.w3.org/2002/07/owl#onProperty"
_OWL_SOME_VALUES_FROM = "http://www.w3.org/2002/07/owl#someValuesFrom"

_PREDICATES_BY_MAPPING_TYPE = {
    "class_mapping": {
        RDFS_SUBCLASS_OF,
        OWL_EQUIVALENT_CLASS,
    },
    "object_property_mapping": {
        RDFS_SUBPROPERTY_OF,
        OWL_EQUIVALENT_PROPERTY,
    },
    "property_chain": {
        OWL_PROPERTY_CHAIN_AXIOM,
    },
    "domain": {
        RDFS_DOMAIN,
    },
    "range": {
        RDFS_RANGE,
    },
    "explicit_blank": {
        None,
    },
}


class MappingCompileError(ValueError):
    """A governed mapping record cannot be rendered as valid Turtle."""


def _iri_term(
    value: str | None,
    field: str,
) -> str:
    if not isinstance(value, str) or not value:
        raise MappingCompileError(
            f"{field} must be a nonempty IRI"
        )

    try:
        return canonical_iri_term(
            value
        )
    except (TypeError, ValueError) as exc:
        raise MappingCompileError(
            f"{field} must be a nonempty IRI"
        ) from exc


def _canonical_expression_key(
    node: ExpressionNode,
) -> str:
    try:
        return canonicalize_expression(
            node
        )
    except (
        MappingExpressionError,
        TypeError,
        ValueError,
    ) as exc:
        raise MappingCompileError(
            f"invalid class expression: {exc}"
        ) from exc


def _flatten_boolean(
    node: ExpressionNode,
) -> tuple[ExpressionNode, ...]:
    children: list[ExpressionNode] = []

    for child in node.children:
        if child.kind == node.kind:
            children.extend(
                _flatten_boolean(
                    child
                )
            )
        else:
            children.append(
                child
            )

    return tuple(
        children
    )


def _render_boolean_expression(
    node: ExpressionNode,
) -> str:
    representatives: dict[
        str,
        ExpressionNode,
    ] = {}

    for child in _flatten_boolean(
        node
    ):
        key = _canonical_expression_key(
            child
        )
        representatives.setdefault(
            key,
            child,
        )

    if not representatives:
        raise MappingCompileError(
            f"{node.kind} expression has no operands"
        )

    ordered = tuple(
        representatives[key]
        for key in sorted(
            representatives
        )
    )

    if len(ordered) == 1:
        return _render_expression(
            ordered[0]
        )

    predicate = (
        _OWL_INTERSECTION_OF
        if node.kind == "intersection"
        else _OWL_UNION_OF
    )
    operands = " ".join(
        _render_expression(
            child
        )
        for child in ordered
    )

    return (
        f"[ <{_RDF_TYPE}> <{_OWL_CLASS}> ; "
        f"<{predicate}> ( {operands} ) ]"
    )


def _render_expression(
    node: ExpressionNode,
) -> str:
    _canonical_expression_key(
        node
    )

    if node.kind == "named":
        return _iri_term(
            node.iri,
            "named class IRI",
        )

    if node.kind in {
        "intersection",
        "union",
    }:
        return _render_boolean_expression(
            node
        )

    if node.kind == "some":
        if (
            node.property_iri is None
            or node.filler is None
        ):
            raise MappingCompileError(
                "existential restriction lacks a property or filler"
            )

        return (
            f"[ <{_RDF_TYPE}> <{_OWL_RESTRICTION}> ; "
            f"<{_OWL_ON_PROPERTY}> "
            f"{_iri_term(node.property_iri, 'restriction property IRI')} ; "
            f"<{_OWL_SOME_VALUES_FROM}> "
            f"{_render_expression(node.filler)} ]"
        )

    raise MappingCompileError(
        "unsupported expression node kind "
        f"{node.kind!r}"
    )


def _validate_record_shape(
    record: GovernedMappingRecord,
) -> None:
    allowed_predicates = (
        _PREDICATES_BY_MAPPING_TYPE.get(
            record.mapping_type
        )
    )

    if allowed_predicates is None:
        raise MappingCompileError(
            "unsupported mapping type "
            f"{record.mapping_type!r}"
        )

    if record.predicate_iri not in allowed_predicates:
        raise MappingCompileError(
            f"mapping type {record.mapping_type!r} "
            "is incompatible with predicate "
            f"{record.predicate_iri!r}"
        )

    if record.mapping_type == "explicit_blank":
        if record.target_source_count:
            raise MappingCompileError(
                "explicit blank record contains a semantic target"
            )
        return

    if record.mapping_type in {
        "class_mapping",
        "domain",
        "range",
    }:
        if (
            record.expression is None
            or record.target_property_iri is not None
            or record.property_chain
        ):
            raise MappingCompileError(
                f"{record.mapping_type} requires exactly "
                "one class-expression target"
            )
        return

    if record.mapping_type == "object_property_mapping":
        if (
            record.expression is not None
            or record.target_property_iri is None
            or record.property_chain
        ):
            raise MappingCompileError(
                "object_property_mapping requires exactly "
                "one property target"
            )
        return

    if (
        record.expression is not None
        or record.target_property_iri is not None
        or len(record.property_chain) < 2
    ):
        raise MappingCompileError(
            "property_chain requires at least two property targets"
        )


def render_mapping_record_turtle(
    record: GovernedMappingRecord,
) -> bytes:
    """Render one governed mapping as deterministic full-IRI Turtle bytes."""

    _validate_record_shape(
        record
    )
    subject = _iri_term(
        record.subject_iri,
        "subject IRI",
    )

    if record.mapping_type == "explicit_blank":
        return b""

    predicate = _iri_term(
        record.predicate_iri,
        "predicate IRI",
    )

    if record.mapping_type in {
        "class_mapping",
        "domain",
        "range",
    }:
        assert record.expression is not None
        target = _render_expression(
            record.expression
        )
    elif record.mapping_type == "object_property_mapping":
        target = _iri_term(
            record.target_property_iri,
            "target property IRI",
        )
    else:
        target = "( " + " ".join(
            _iri_term(
                value,
                "property-chain IRI",
            )
            for value in record.property_chain
        ) + " )"

    return (
        f"{subject} {predicate} {target} .\n"
    ).encode(
        "utf-8"
    )
