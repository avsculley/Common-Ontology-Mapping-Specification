"""Project-neutral COMS mapping-expression model and canonicalization."""

from __future__ import annotations

from dataclasses import dataclass
import unicodedata


@dataclass(frozen=True)
class ExpressionNode:
    kind: str
    iri: str | None = None
    children: tuple["ExpressionNode", ...] = ()
    property_iri: str | None = None
    filler: "ExpressionNode | None" = None


class MappingExpressionError(ValueError):
    """A mapping expression cannot be canonically represented."""


def normalize_nfc(
    value: str,
) -> str:
    """Normalize mapping-expression lexical content to NFC."""

    return unicodedata.normalize(
        "NFC",
        value,
    )


def canonical_iri_term(
    value: str,
) -> str:
    """Render one canonical full-IRI functional-syntax term."""

    normalized = normalize_nfc(
        value
    )

    if not normalized:
        raise ValueError(
            "IRI must be nonempty"
        )

    return f"<{normalized}>"


def _flatten(
    node: ExpressionNode,
    kind: str,
) -> tuple[
    ExpressionNode,
    ...,
]:
    flattened: list[
        ExpressionNode
    ] = []

    for child in node.children:
        if child.kind == kind:
            flattened.extend(
                _flatten(
                    child,
                    kind,
                )
            )
        else:
            flattened.append(
                child
            )

    return tuple(
        flattened
    )


def canonicalize_expression(
    node: ExpressionNode,
) -> str:
    """Return the canonical functional-syntax representation of an expression."""

    if node.kind == "named":
        if node.iri is None:
            raise MappingExpressionError(
                "named expression lacks an IRI"
            )

        return canonical_iri_term(
            node.iri
        )

    if node.kind in {
        "intersection",
        "union",
    }:
        flattened = _flatten(
            node,
            node.kind,
        )

        if not flattened:
            raise MappingExpressionError(
                f"{node.kind} expression has no operands"
            )

        operands = sorted(
            {
                canonicalize_expression(
                    child
                )
                for child
                in flattened
            }
        )

        if len(
            operands
        ) == 1:
            return operands[
                0
            ]

        operator = (
            "ObjectIntersectionOf"
            if node.kind
            == "intersection"
            else "ObjectUnionOf"
        )

        return (
            f"{operator}("
            f"{' '.join(operands)}"
            ")"
        )

    if node.kind == "some":
        if (
            node.property_iri
            is None
            or node.filler
            is None
        ):
            raise MappingExpressionError(
                "existential restriction lacks "
                "a property or filler"
            )

        filler = (
            canonicalize_expression(
                node.filler
            )
        )

        return (
            "ObjectSomeValuesFrom("
            f"{canonical_iri_term(node.property_iri)} "
            f"{filler}"
            ")"
        )

    raise MappingExpressionError(
        "unsupported expression node kind "
        f"{node.kind!r}"
    )
