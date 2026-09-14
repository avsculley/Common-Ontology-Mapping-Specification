from pathlib import Path
import re
import unittest

from coms.mapping_expression import (
    ExpressionNode,
)
from coms.mapping_parser import (
    ENTITY_CLASS,
    ENTITY_OBJECT_PROPERTY,
    EntityResolutionError,
    MappingParseError,
)
from coms.mapping_record import (
    GovernedMappingRecord,
)
from coms.mapping_record_builder import (
    MappingRecordBuildError,
    build_governed_mapping_record,
)
from coms.row_identity import (
    OWL_EQUIVALENT_CLASS,
    OWL_EQUIVALENT_PROPERTY,
    OWL_PROPERTY_CHAIN_AXIOM,
    RDFS_DOMAIN,
    RDFS_RANGE,
    RDFS_SUBCLASS_OF,
    RDFS_SUBPROPERTY_OF,
    RowLocation,
    build_row_audit,
    canonical_input_for_mapping_record,
)


ROW_ID = "urn:uuid:123e4567-e89b-42d3-a456-426614174000"
CLASS_SOURCE = "urn:example:SourceClass"
PROPERTY_SOURCE = "urn:example:source-property"


class DictResolver:
    def __init__(
        self,
        values: dict[tuple[str, str], str],
    ):
        self.values = values
        self.calls: list[tuple[str, str]] = []

    def resolve_entity(
        self,
        token: str,
        expected_kind: str,
    ) -> str:
        self.calls.append(
            (
                token,
                expected_kind,
            )
        )
        key = (
            token,
            expected_kind,
        )
        if key not in self.values:
            raise EntityResolutionError(
                f"cannot resolve {token!r} as {expected_kind}"
            )
        return self.values[key]


def resolver() -> DictResolver:
    return DictResolver(
        {
            ("ex:Class", ENTITY_CLASS): "urn:example:Class",
            ("ex:Other", ENTITY_CLASS): "urn:example:Other",
            ("ex:property", ENTITY_OBJECT_PROPERTY): "urn:example:property",
            ("ex:first", ENTITY_OBJECT_PROPERTY): "urn:example:first",
            ("ex:second", ENTITY_OBJECT_PROPERTY): "urn:example:second",
        }
    )


def build(
    entity_resolver: DictResolver,
    *,
    subject_iri: str = CLASS_SOURCE,
    subject_kind: str = ENTITY_CLASS,
    predicate_iri: str | None = RDFS_SUBCLASS_OF,
    target_text: str = "ex:Class",
    reasoning: str = "",
) -> GovernedMappingRecord:
    return build_governed_mapping_record(
        row_id=ROW_ID,
        subject_iri=subject_iri,
        subject_kind=subject_kind,
        predicate_iri=predicate_iri,
        target_text=target_text,
        resolver=entity_resolver,
        reasoning=reasoning,
    )


class MappingRecordBuilderTests(unittest.TestCase):
    def test_builds_subclass_mapping_and_preserves_reasoning(self):
        record = build(
            resolver(),
            reasoning="reviewed rationale",
        )

        self.assertEqual(record.mapping_type, "class_mapping")
        self.assertEqual(record.predicate_iri, RDFS_SUBCLASS_OF)
        self.assertEqual(record.reasoning, "reviewed rationale")
        self.assertEqual(
            record.expression,
            ExpressionNode(
                kind="named",
                iri="urn:example:Class",
            ),
        )

    def test_builds_equivalent_class_mapping(self):
        record = build(
            resolver(),
            predicate_iri=OWL_EQUIVALENT_CLASS,
        )

        self.assertEqual(record.mapping_type, "class_mapping")
        self.assertEqual(record.predicate_iri, OWL_EQUIVALENT_CLASS)
        self.assertIsNotNone(record.expression)

    def test_builds_subproperty_mapping(self):
        record = build(
            resolver(),
            subject_iri=PROPERTY_SOURCE,
            subject_kind=ENTITY_OBJECT_PROPERTY,
            predicate_iri=RDFS_SUBPROPERTY_OF,
            target_text="ex:property",
        )

        self.assertEqual(record.mapping_type, "object_property_mapping")
        self.assertEqual(record.target_property_iri, "urn:example:property")

    def test_builds_equivalent_property_mapping(self):
        record = build(
            resolver(),
            subject_iri=PROPERTY_SOURCE,
            subject_kind=ENTITY_OBJECT_PROPERTY,
            predicate_iri=OWL_EQUIVALENT_PROPERTY,
            target_text="ex:property",
        )

        self.assertEqual(record.mapping_type, "object_property_mapping")
        self.assertEqual(record.predicate_iri, OWL_EQUIVALENT_PROPERTY)
        self.assertEqual(record.target_property_iri, "urn:example:property")

    def test_builds_ordered_property_chain(self):
        record = build(
            resolver(),
            subject_iri=PROPERTY_SOURCE,
            subject_kind=ENTITY_OBJECT_PROPERTY,
            predicate_iri=OWL_PROPERTY_CHAIN_AXIOM,
            target_text="ex:first o ex:second",
        )

        self.assertEqual(record.mapping_type, "property_chain")
        self.assertEqual(
            record.property_chain,
            (
                "urn:example:first",
                "urn:example:second",
            ),
        )

    def test_builds_domain_mapping(self):
        record = build(
            resolver(),
            subject_iri=PROPERTY_SOURCE,
            subject_kind=ENTITY_OBJECT_PROPERTY,
            predicate_iri=RDFS_DOMAIN,
        )

        self.assertEqual(record.mapping_type, "domain")
        self.assertIsNotNone(record.expression)

    def test_builds_range_mapping(self):
        record = build(
            resolver(),
            subject_iri=PROPERTY_SOURCE,
            subject_kind=ENTITY_OBJECT_PROPERTY,
            predicate_iri=RDFS_RANGE,
        )

        self.assertEqual(record.mapping_type, "range")
        self.assertIsNotNone(record.expression)

    def test_builds_explicit_blank(self):
        record = build(
            resolver(),
            predicate_iri=None,
            target_text="  ",
            reasoning="intentionally unmapped",
        )

        self.assertEqual(record.mapping_type, "explicit_blank")
        self.assertIsNone(record.predicate_iri)
        self.assertEqual(record.reasoning, "intentionally unmapped")
        self.assertEqual(record.target_source_count, 0)

    def test_rejects_incompatible_subject_kinds(self):
        cases = (
            (
                RDFS_SUBCLASS_OF,
                ENTITY_OBJECT_PROPERTY,
                "ex:Class",
            ),
            (
                RDFS_SUBPROPERTY_OF,
                ENTITY_CLASS,
                "ex:property",
            ),
            (
                OWL_PROPERTY_CHAIN_AXIOM,
                ENTITY_CLASS,
                "ex:first o ex:second",
            ),
            (
                RDFS_DOMAIN,
                ENTITY_CLASS,
                "ex:Class",
            ),
            (
                RDFS_RANGE,
                ENTITY_CLASS,
                "ex:Class",
            ),
        )

        for predicate_iri, subject_kind, target_text in cases:
            with self.subTest(predicate_iri=predicate_iri):
                with self.assertRaisesRegex(
                    MappingRecordBuildError,
                    "requires subject kind",
                ):
                    build(
                        resolver(),
                        subject_kind=subject_kind,
                        predicate_iri=predicate_iri,
                        target_text=target_text,
                    )

    def test_rejects_unsupported_predicate(self):
        with self.assertRaisesRegex(
            MappingRecordBuildError,
            "unsupported mapping predicate",
        ):
            build(
                resolver(),
                predicate_iri="urn:example:unsupported",
            )

    def test_rejects_blank_target_for_active_mapping(self):
        with self.assertRaisesRegex(
            MappingRecordBuildError,
            "active mapping requires target text",
        ):
            build(
                resolver(),
                target_text=" \t ",
            )

    def test_rejects_target_for_explicit_blank(self):
        with self.assertRaisesRegex(
            MappingRecordBuildError,
            "explicit blank mapping cannot contain target text",
        ):
            build(
                resolver(),
                predicate_iri=None,
                target_text="ex:Class",
            )

    def test_parser_errors_propagate(self):
        with self.assertRaises(MappingParseError):
            build(
                resolver(),
                target_text="(ex:Class",
            )

    def test_entity_resolution_errors_propagate(self):
        with self.assertRaises(EntityResolutionError):
            build(
                resolver(),
                target_text="missing:Class",
            )

    def test_record_flows_to_canonical_axiom_identity(self):
        entity_resolver = DictResolver(
            {
                ("ex:Material", ENTITY_CLASS): "urn:example:Material",
                ("ex:hasFunction", ENTITY_OBJECT_PROPERTY): (
                    "urn:example:hasFunction"
                ),
                ("ex:Sensing", ENTITY_CLASS): "urn:example:Sensing",
            }
        )
        record = build_governed_mapping_record(
            row_id=ROW_ID,
            subject_iri=CLASS_SOURCE,
            subject_kind=ENTITY_CLASS,
            predicate_iri=RDFS_SUBCLASS_OF,
            target_text=(
                "ex:Material and "
                "(ex:hasFunction some ex:Sensing)"
            ),
            resolver=entity_resolver,
            reasoning="synthetic end-to-end mapping",
        )

        self.assertIsInstance(record, GovernedMappingRecord)
        audit = build_row_audit(
            canonical_input_for_mapping_record(
                record,
                RowLocation("Synthetic", 2),
            )
        )
        self.assertEqual(
            audit.authoritative_axioms[0].canonical_axiom,
            (
                "SubClassOf("
                "<urn:example:SourceClass> "
                "ObjectIntersectionOf("
                "<urn:example:Material> "
                "ObjectSomeValuesFrom("
                "<urn:example:hasFunction> "
                "<urn:example:Sensing>"
                ")"
                ")"
                ")"
            ),
        )

    def test_implementation_is_project_and_source_format_neutral(self):
        sources = "\n".join(
            Path(path).read_text(encoding="utf-8")
            for path in (
                "src/coms/mapping_predicates.py",
                "src/coms/mapping_record_builder.py",
            )
        )

        for value in (
            "openpyxl",
            "rdflib",
            "Workbook",
            "Worksheet",
            "URIRef",
            "Graph",
        ):
            self.assertNotIn(value, sources)

        project_pattern = re.compile(
            r"\b(?:SSN|SOSA|PROV|BFO|CCO|RO|HermiT)\b",
            re.IGNORECASE,
        )
        self.assertIsNone(project_pattern.search(sources))
