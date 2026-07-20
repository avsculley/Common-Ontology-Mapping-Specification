#!/usr/bin/env python3
"""Project-neutral tests for COMS row identity and canonicalization."""

from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from coms import row_identity as identity  # noqa: E402


ROW_ID_1 = "urn:uuid:123e4567-e89b-42d3-a456-426614174000"
ROW_ID_2 = "urn:uuid:123e4567-e89b-42d3-b456-426614174001"

SOURCE = "urn:example:Source"
TARGET = "urn:example:Target"
PROPERTY_1 = "urn:example:property-1"
PROPERTY_2 = "urn:example:property-2"


def location(row_number: int = 2) -> identity.RowLocation:
    return identity.RowLocation("Mappings", row_number)


def named(iri: str) -> identity.ExpressionNode:
    return identity.ExpressionNode(kind="named", iri=iri)


def intersection(
    *children: identity.ExpressionNode,
) -> identity.ExpressionNode:
    return identity.ExpressionNode(
        kind="intersection",
        children=tuple(children),
    )


def some(
    property_iri: str,
    filler: identity.ExpressionNode,
) -> identity.ExpressionNode:
    return identity.ExpressionNode(
        kind="some",
        property_iri=property_iri,
        filler=filler,
    )


def class_row(
    *,
    row_id: str = ROW_ID_1,
    row_number: int = 2,
    subject: str = SOURCE,
    predicate: str = identity.RDFS_SUBCLASS_OF,
    expression: identity.ExpressionNode | None = None,
) -> identity.CanonicalRowInput:
    return identity.CanonicalRowInput(
        row_id=row_id,
        location=location(row_number),
        subject_iri=subject,
        predicate_iri=predicate,
        mapping_type="class_mapping",
        reasoning="Synthetic test mapping.",
        expression=expression or named(TARGET),
    )


class RowIdentityTests(unittest.TestCase):
    def test_canonical_uuid4_urn_is_accepted(self) -> None:
        self.assertEqual(
            identity.validate_row_id(ROW_ID_1, location()),
            ROW_ID_1,
        )

    def test_missing_row_id_has_structured_error(self) -> None:
        with self.assertRaises(identity.ComsRowIdentityError) as context:
            identity.validate_row_id("", location(7))

        issue = context.exception.issues[0]
        self.assertEqual(issue.code, "MISSING_ROW_ID")
        self.assertEqual(issue.location, location(7))

    def test_noncanonical_row_id_is_rejected(self) -> None:
        with self.assertRaises(identity.ComsRowIdentityError) as context:
            identity.validate_row_id(ROW_ID_1.upper(), location())

        self.assertEqual(
            context.exception.issues[0].code,
            "MALFORMED_ROW_ID",
        )

    def test_intersection_is_flattened_deduplicated_and_sorted(self) -> None:
        expression = intersection(
            named("urn:example:Z"),
            intersection(
                named("urn:example:A"),
                named("urn:example:Z"),
            ),
        )

        canonical = identity.canonicalize_processed_row(
            class_row(expression=expression)
        )

        self.assertEqual(
            canonical.target,
            "ObjectIntersectionOf(<urn:example:A> <urn:example:Z>)",
        )

    def test_existential_restriction_is_canonicalized(self) -> None:
        canonical = identity.canonicalize_processed_row(
            class_row(
                expression=some(
                    PROPERTY_1,
                    named(TARGET),
                )
            )
        )

        self.assertEqual(
            canonical.target,
            "ObjectSomeValuesFrom("
            "<urn:example:property-1> "
            "<urn:example:Target>"
            ")",
        )

    def test_unicode_is_normalized_to_nfc(self) -> None:
        decomposed = "urn:example:cafe\u0301"

        canonical = identity.canonicalize_processed_row(
            class_row(
                subject=decomposed,
                expression=named(decomposed),
            )
        )

        self.assertEqual(canonical.subject_iri, "urn:example:café")
        self.assertEqual(canonical.target, "<urn:example:café>")

    def test_hash_is_stable_across_operand_order(self) -> None:
        first = identity.canonicalize_processed_row(
            class_row(
                expression=intersection(
                    named("urn:example:A"),
                    named("urn:example:B"),
                )
            )
        )
        second = identity.canonicalize_processed_row(
            class_row(
                expression=intersection(
                    named("urn:example:B"),
                    named("urn:example:A"),
                )
            )
        )

        self.assertEqual(first, second)
        self.assertEqual(
            identity.source_expression_sha256(first),
            identity.source_expression_sha256(second),
        )

    def test_class_mapping_produces_authoritative_axiom(self) -> None:
        axioms = identity.canonical_authoritative_axioms(class_row())

        self.assertEqual(len(axioms), 1)
        self.assertEqual(
            axioms[0].canonical_axiom,
            "SubClassOf("
            "<urn:example:Source> "
            "<urn:example:Target>"
            ")",
        )
        self.assertEqual(len(axioms[0].sha256), 64)

    def test_property_chain_produces_authoritative_axiom(self) -> None:
        row = identity.CanonicalRowInput(
            row_id=ROW_ID_1,
            location=location(),
            subject_iri="urn:example:super-property",
            predicate_iri=identity.OWL_PROPERTY_CHAIN_AXIOM,
            mapping_type="property_chain",
            property_chain=(PROPERTY_1, PROPERTY_2),
        )

        axioms = identity.canonical_authoritative_axioms(row)

        self.assertEqual(
            axioms[0].canonical_axiom,
            "SubObjectPropertyOf("
            "ObjectPropertyChain("
            "<urn:example:property-1> "
            "<urn:example:property-2>"
            ") "
            "<urn:example:super-property>"
            ")",
        )

    def test_explicit_blank_has_no_authoritative_axiom(self) -> None:
        row = identity.CanonicalRowInput(
            row_id=ROW_ID_1,
            location=location(),
            subject_iri=SOURCE,
            predicate_iri=None,
            mapping_type="explicit_blank",
        )

        canonical = identity.canonicalize_processed_row(row)

        self.assertIsNone(canonical.target)
        self.assertEqual(
            identity.canonical_authoritative_axioms(row),
            (),
        )

    def test_multiple_target_representations_are_rejected(self) -> None:
        row = replace(
            class_row(),
            target_property_iri=PROPERTY_1,
        )

        with self.assertRaises(identity.ComsRowIdentityError) as context:
            identity.canonicalize_processed_row(row)

        self.assertEqual(
            context.exception.issues[0].code,
            "UNSUPPORTED_CANONICAL_EXPRESSION",
        )

    def test_duplicate_row_ids_are_reported_deterministically(self) -> None:
        issues = identity.validate_unique_row_ids(
            (
                identity.RowIdentityReference(
                    row_id=ROW_ID_1,
                    location=location(9),
                ),
                identity.RowIdentityReference(
                    row_id=ROW_ID_1,
                    location=location(3),
                ),
            )
        )

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].code, "DUPLICATE_ROW_ID")
        self.assertEqual(issues[0].location, location(9))
        self.assertIn("Mappings!3", issues[0].message)

    def test_duplicate_authoritative_axioms_are_reported(self) -> None:
        first = identity.build_row_audit(
            class_row(
                row_id=ROW_ID_1,
                row_number=2,
            )
        )
        second = identity.build_row_audit(
            class_row(
                row_id=ROW_ID_2,
                row_number=4,
            )
        )

        issues = identity.validate_unique_authoritative_axioms(
            (second, first)
        )

        self.assertEqual(len(issues), 1)
        self.assertEqual(
            issues[0].code,
            "DUPLICATE_AUTHORITATIVE_AXIOM",
        )
        self.assertEqual(issues[0].row_id, ROW_ID_2)
        self.assertEqual(issues[0].location, location(4))
        self.assertIn(ROW_ID_1, issues[0].message)


if __name__ == "__main__":
    unittest.main()
