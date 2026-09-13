from dataclasses import (
    FrozenInstanceError,
    fields,
)
from pathlib import Path
import re
import unittest

from coms.mapping_expression import (
    ExpressionNode,
)
from coms.mapping_record import (
    GovernedMappingRecord,
)
from coms.row_identity import (
    OWL_EQUIVALENT_CLASS,
    OWL_PROPERTY_CHAIN_AXIOM,
    RDFS_SUBCLASS_OF,
    RDFS_SUBPROPERTY_OF,
    RowLocation,
    build_row_audit,
    canonical_input_for_mapping_record,
)


ROW_ID = (
    "urn:uuid:"
    "123e4567-e89b-42d3-a456-426614174000"
)


def location(
    row_number: int = 2,
) -> RowLocation:
    return RowLocation(
        "Mappings",
        row_number,
    )


class GovernedMappingRecordTests(
    unittest.TestCase
):
    def test_model_is_frozen_and_contains_semantic_fields_only(
        self,
    ):
        record = GovernedMappingRecord(
            row_id=ROW_ID,
            subject_iri=(
                "urn:example:Source"
            ),
            predicate_iri=(
                RDFS_SUBCLASS_OF
            ),
            mapping_type=(
                "class_mapping"
            ),
            expression=ExpressionNode(
                kind="named",
                iri="urn:example:Target",
            ),
        )

        self.assertEqual(
            tuple(
                field.name
                for field
                in fields(
                    GovernedMappingRecord
                )
            ),
            (
                "row_id",
                "subject_iri",
                "predicate_iri",
                "mapping_type",
                "reasoning",
                "expression",
                "target_property_iri",
                "property_chain",
            ),
        )

        with self.assertRaises(
            FrozenInstanceError
        ):
            record.subject_iri = (
                "urn:example:Other"
            )

    def test_class_expression_record_adapts_without_semantic_change(
        self,
    ):
        expression = ExpressionNode(
            kind="named",
            iri="urn:example:Target",
        )

        record = GovernedMappingRecord(
            row_id=ROW_ID,
            subject_iri=(
                "urn:example:Source"
            ),
            predicate_iri=(
                OWL_EQUIVALENT_CLASS
            ),
            mapping_type=(
                "class_mapping"
            ),
            reasoning="reviewed mapping",
            expression=expression,
        )

        adapted = (
            canonical_input_for_mapping_record(
                record,
                location(),
            )
        )

        self.assertEqual(
            adapted.row_id,
            record.row_id,
        )
        self.assertEqual(
            adapted.subject_iri,
            record.subject_iri,
        )
        self.assertEqual(
            adapted.predicate_iri,
            record.predicate_iri,
        )
        self.assertEqual(
            adapted.mapping_type,
            record.mapping_type,
        )
        self.assertEqual(
            adapted.reasoning,
            record.reasoning,
        )
        self.assertIs(
            adapted.expression,
            expression,
        )

    def test_property_target_record_adapts_without_semantic_change(
        self,
    ):
        record = GovernedMappingRecord(
            row_id=ROW_ID,
            subject_iri=(
                "urn:example:source-property"
            ),
            predicate_iri=(
                RDFS_SUBPROPERTY_OF
            ),
            mapping_type=(
                "object_property_mapping"
            ),
            target_property_iri=(
                "urn:example:target-property"
            ),
        )

        adapted = (
            canonical_input_for_mapping_record(
                record,
                location(),
            )
        )

        self.assertEqual(
            adapted.target_property_iri,
            (
                "urn:example:target-property"
            ),
        )
        self.assertIsNone(
            adapted.expression
        )
        self.assertEqual(
            adapted.property_chain,
            (),
        )

    def test_property_chain_order_is_preserved(
        self,
    ):
        chain = (
            "urn:example:first",
            "urn:example:second",
            "urn:example:third",
        )

        record = GovernedMappingRecord(
            row_id=ROW_ID,
            subject_iri=(
                "urn:example:super-property"
            ),
            predicate_iri=(
                OWL_PROPERTY_CHAIN_AXIOM
            ),
            mapping_type=(
                "property_chain"
            ),
            property_chain=chain,
        )

        self.assertEqual(
            record.target_source_count,
            1,
        )

        adapted = (
            canonical_input_for_mapping_record(
                record,
                location(),
            )
        )

        self.assertEqual(
            adapted.property_chain,
            chain,
        )

    def test_explicit_blank_record_has_no_semantic_target(
        self,
    ):
        record = GovernedMappingRecord(
            row_id=ROW_ID,
            subject_iri=(
                "urn:example:Source"
            ),
            predicate_iri=None,
            mapping_type=(
                "explicit_blank"
            ),
            reasoning=(
                "intentionally unmapped"
            ),
        )

        self.assertEqual(
            record.target_source_count,
            0,
        )

        audit = build_row_audit(
            canonical_input_for_mapping_record(
                record,
                location(),
            )
        )

        self.assertEqual(
            audit.authoritative_axioms,
            (),
        )

    def test_physical_location_is_not_part_of_governed_record(
        self,
    ):
        names = {
            field.name
            for field
            in fields(
                GovernedMappingRecord
            )
        }

        self.assertNotIn(
            "sheet",
            names,
        )
        self.assertNotIn(
            "row_number",
            names,
        )
        self.assertNotIn(
            "location",
            names,
        )

    def test_reasoning_and_location_do_not_change_expression_hash(
        self,
    ):
        first = GovernedMappingRecord(
            row_id=ROW_ID,
            subject_iri=(
                "urn:example:Source"
            ),
            predicate_iri=(
                RDFS_SUBCLASS_OF
            ),
            mapping_type=(
                "class_mapping"
            ),
            reasoning="first rationale",
            expression=ExpressionNode(
                kind="named",
                iri="urn:example:Target",
            ),
        )

        second = GovernedMappingRecord(
            row_id=ROW_ID,
            subject_iri=(
                "urn:example:Source"
            ),
            predicate_iri=(
                RDFS_SUBCLASS_OF
            ),
            mapping_type=(
                "class_mapping"
            ),
            reasoning="second rationale",
            expression=ExpressionNode(
                kind="named",
                iri="urn:example:Target",
            ),
        )

        first_audit = build_row_audit(
            canonical_input_for_mapping_record(
                first,
                location(
                    2
                ),
            )
        )

        second_audit = build_row_audit(
            canonical_input_for_mapping_record(
                second,
                location(
                    999
                ),
            )
        )

        self.assertEqual(
            first_audit.source_expression_sha256,
            second_audit.source_expression_sha256,
        )
        self.assertEqual(
            first_audit.authoritative_axioms,
            second_audit.authoritative_axioms,
        )
        self.assertNotEqual(
            first_audit.reasoning,
            second_audit.reasoning,
        )
        self.assertNotEqual(
            first_audit.location,
            second_audit.location,
        )

    def test_module_is_project_and_workbook_implementation_neutral(
        self,
    ):
        source = Path(
            "src/coms/mapping_record.py"
        ).read_text(
            encoding="utf-8"
        )

        for value in (
            "openpyxl",
            "rdflib",
            "Workbook",
            "Worksheet",
            "URIRef",
        ):
            self.assertNotIn(
                value,
                source,
            )

        project_pattern = re.compile(
            r"\b(?:SSN|SOSA|PROV|BFO|CCO|RO|HermiT)\b",
            re.IGNORECASE,
        )

        self.assertIsNone(
            project_pattern.search(
                source
            )
        )
