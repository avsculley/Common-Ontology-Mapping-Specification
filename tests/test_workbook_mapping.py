import ast
from pathlib import Path
import re
import subprocess
import sys
import unittest

from coms.adapters.xlsx import WorkbookSourceRow
from coms.mapping_compiler import render_mapping_record_turtle
from coms.mapping_expression import ExpressionNode
from coms.mapping_parser import (
    ENTITY_CLASS,
    ENTITY_OBJECT_PROPERTY,
    EntityResolutionError,
    MappingParseError,
)
from coms.mapping_predicates import (
    MappingPredicateTokenError,
    OWL_EQUIVALENT_CLASS,
    OWL_EQUIVALENT_PROPERTY,
    OWL_PROPERTY_CHAIN_AXIOM,
    RDFS_DOMAIN,
    RDFS_RANGE,
    RDFS_SUBCLASS_OF,
    RDFS_SUBPROPERTY_OF,
    normalize_mapping_predicate_token,
)
from coms.mapping_record import GovernedMappingRecord
from coms.mapping_record_builder import MappingRecordBuildError
from coms.row_identity import (
    RowLocation,
    build_row_audit,
    canonical_input_for_mapping_record,
)
from coms.workbook_mapping import (
    ResolvedSourceEntity,
    WorkbookMappingError,
    build_governed_mapping_record_from_workbook_row,
)


ROW_ID = "urn:uuid:123e4567-e89b-42d3-a456-426614174000"
SOURCE_CLASS = "urn:example:SourceClass"
SOURCE_PROPERTY = "urn:example:source-property"
TARGET_CLASS = "urn:example:TargetClass"
TARGET_PROPERTY = "urn:example:target-property"
FIRST_PROPERTY = "urn:example:first-property"
SECOND_PROPERTY = "urn:example:second-property"

PREDICATE_CASES = (
    ("rdfs:subClassOf", RDFS_SUBCLASS_OF),
    ("owl:equivalentClass", OWL_EQUIVALENT_CLASS),
    ("rdfs:subPropertyOf", RDFS_SUBPROPERTY_OF),
    ("owl:equivalentProperty", OWL_EQUIVALENT_PROPERTY),
    ("owl:propertyChainAxiom", OWL_PROPERTY_CHAIN_AXIOM),
    ("rdfs:domain", RDFS_DOMAIN),
    ("rdfs:range", RDFS_RANGE),
)


class FakeSourceResolver:
    def __init__(
        self,
        result: ResolvedSourceEntity | None = None,
        error: Exception | None = None,
    ):
        self.result = result or ResolvedSourceEntity(
            SOURCE_CLASS,
            ENTITY_CLASS,
        )
        self.error = error
        self.calls: list[str] = []

    def resolve_source_entity(
        self,
        token: str,
    ) -> ResolvedSourceEntity:
        self.calls.append(token)

        if self.error is not None:
            raise self.error

        return self.result


class FakeTargetResolver:
    def __init__(self):
        self.values = {
            ("ex:Class", ENTITY_CLASS): TARGET_CLASS,
            ("ex:property", ENTITY_OBJECT_PROPERTY): TARGET_PROPERTY,
            ("ex:first", ENTITY_OBJECT_PROPERTY): FIRST_PROPERTY,
            ("ex:second", ENTITY_OBJECT_PROPERTY): SECOND_PROPERTY,
            ("ex:Material", ENTITY_CLASS): "urn:example:Material",
            ("ex:hasFunction", ENTITY_OBJECT_PROPERTY): (
                "urn:example:hasFunction"
            ),
            ("ex:SensingFunction", ENTITY_CLASS): (
                "urn:example:SensingFunction"
            ),
        }
        self.calls: list[tuple[str, str]] = []

    def resolve_entity(
        self,
        token: str,
        expected_kind: str,
    ) -> str:
        self.calls.append((token, expected_kind))
        key = (token, expected_kind)

        if key not in self.values:
            raise EntityResolutionError(
                f"cannot resolve {token!r} as {expected_kind}"
            )

        return self.values[key]


def source_row(
    *,
    subject: str = "src:Source",
    predicate: str = "rdfs:subClassOf",
    target: str = "ex:Class",
    reasoning: str = "because",
    status: str | None = None,
    row_id: str = ROW_ID,
    location: RowLocation = RowLocation("Mappings", 2),
) -> WorkbookSourceRow:
    return WorkbookSourceRow(
        location=location,
        row_id_text=row_id,
        subject_text=subject,
        predicate_text=predicate,
        target_text=target,
        reasoning_text=reasoning,
        status_text=status,
    )


def property_source_resolver() -> FakeSourceResolver:
    return FakeSourceResolver(
        ResolvedSourceEntity(
            SOURCE_PROPERTY,
            ENTITY_OBJECT_PROPERTY,
        )
    )


def build(
    row: WorkbookSourceRow,
    source_resolver: FakeSourceResolver | None = None,
    target_resolver: FakeTargetResolver | None = None,
) -> GovernedMappingRecord:
    return build_governed_mapping_record_from_workbook_row(
        row,
        source_resolver or FakeSourceResolver(),
        target_resolver or FakeTargetResolver(),
    )


class WorkbookMappingTests(unittest.TestCase):
    def test_builds_subclass_mapping(self):
        self.assertEqual(
            build(source_row()),
            GovernedMappingRecord(
                row_id=ROW_ID,
                subject_iri=SOURCE_CLASS,
                predicate_iri=RDFS_SUBCLASS_OF,
                mapping_type="class_mapping",
                reasoning="because",
                expression=ExpressionNode(
                    kind="named",
                    iri=TARGET_CLASS,
                ),
            ),
        )

    def test_builds_equivalent_class_mapping(self):
        self.assertEqual(
            build(
                source_row(
                    predicate="owl:equivalentClass",
                )
            ),
            GovernedMappingRecord(
                row_id=ROW_ID,
                subject_iri=SOURCE_CLASS,
                predicate_iri=OWL_EQUIVALENT_CLASS,
                mapping_type="class_mapping",
                reasoning="because",
                expression=ExpressionNode(
                    kind="named",
                    iri=TARGET_CLASS,
                ),
            ),
        )

    def test_builds_subproperty_mapping(self):
        record = build(
            source_row(
                predicate="rdfs:subPropertyOf",
                target="ex:property",
            ),
            property_source_resolver(),
        )

        self.assertEqual(
            record,
            GovernedMappingRecord(
                row_id=ROW_ID,
                subject_iri=SOURCE_PROPERTY,
                predicate_iri=RDFS_SUBPROPERTY_OF,
                mapping_type="object_property_mapping",
                reasoning="because",
                target_property_iri=TARGET_PROPERTY,
            ),
        )

    def test_builds_equivalent_property_mapping(self):
        record = build(
            source_row(
                predicate="owl:equivalentProperty",
                target="ex:property",
            ),
            property_source_resolver(),
        )

        self.assertEqual(
            record,
            GovernedMappingRecord(
                row_id=ROW_ID,
                subject_iri=SOURCE_PROPERTY,
                predicate_iri=OWL_EQUIVALENT_PROPERTY,
                mapping_type="object_property_mapping",
                reasoning="because",
                target_property_iri=TARGET_PROPERTY,
            ),
        )

    def test_builds_property_chain_mapping(self):
        record = build(
            source_row(
                predicate="owl:propertyChainAxiom",
                target="ex:first o ex:second",
            ),
            property_source_resolver(),
        )

        self.assertEqual(
            record,
            GovernedMappingRecord(
                row_id=ROW_ID,
                subject_iri=SOURCE_PROPERTY,
                predicate_iri=OWL_PROPERTY_CHAIN_AXIOM,
                mapping_type="property_chain",
                reasoning="because",
                property_chain=(
                    FIRST_PROPERTY,
                    SECOND_PROPERTY,
                ),
            ),
        )

    def test_builds_domain_mapping(self):
        record = build(
            source_row(
                predicate="rdfs:domain",
            ),
            property_source_resolver(),
        )

        self.assertEqual(
            record,
            GovernedMappingRecord(
                row_id=ROW_ID,
                subject_iri=SOURCE_PROPERTY,
                predicate_iri=RDFS_DOMAIN,
                mapping_type="domain",
                reasoning="because",
                expression=ExpressionNode(
                    kind="named",
                    iri=TARGET_CLASS,
                ),
            ),
        )

    def test_builds_range_mapping(self):
        record = build(
            source_row(
                predicate="rdfs:range",
            ),
            property_source_resolver(),
        )

        self.assertEqual(
            record,
            GovernedMappingRecord(
                row_id=ROW_ID,
                subject_iri=SOURCE_PROPERTY,
                predicate_iri=RDFS_RANGE,
                mapping_type="range",
                reasoning="because",
                expression=ExpressionNode(
                    kind="named",
                    iri=TARGET_CLASS,
                ),
            ),
        )

    def test_builds_explicit_blank_mapping(self):
        record = build(
            source_row(
                predicate="",
                target="",
            )
        )

        self.assertEqual(
            record,
            GovernedMappingRecord(
                row_id=ROW_ID,
                subject_iri=SOURCE_CLASS,
                predicate_iri=None,
                mapping_type="explicit_blank",
                reasoning="because",
            ),
        )

    def test_predicate_curie_and_full_iri_forms_share_authority(self):
        for curie, iri in PREDICATE_CASES:
            with self.subTest(curie=curie):
                self.assertEqual(
                    normalize_mapping_predicate_token(curie),
                    iri,
                )
                self.assertEqual(
                    normalize_mapping_predicate_token(iri),
                    iri,
                )

    def test_blank_and_surrounding_predicate_whitespace_normalize(self):
        self.assertIsNone(
            normalize_mapping_predicate_token(" \t ")
        )
        self.assertEqual(
            normalize_mapping_predicate_token(
                "  rdfs:subClassOf\n"
            ),
            RDFS_SUBCLASS_OF,
        )

    def test_unknown_predicate_tokens_are_rejected(self):
        for token in (
            "owl:unknownPredicate",
            "https://example.org/unknownPredicate",
            "project:predicate",
        ):
            with self.subTest(token=token):
                with self.assertRaisesRegex(
                    MappingPredicateTokenError,
                    "unsupported mapping predicate token",
                ):
                    normalize_mapping_predicate_token(token)

    def test_class_and_object_property_source_kinds_are_preserved(self):
        class_record = build(source_row())
        property_record = build(
            source_row(
                predicate="rdfs:subPropertyOf",
                target="ex:property",
            ),
            property_source_resolver(),
        )

        self.assertEqual(class_record.subject_iri, SOURCE_CLASS)
        self.assertEqual(property_record.subject_iri, SOURCE_PROPERTY)

    def test_source_resolver_is_called_once(self):
        source_resolver = FakeSourceResolver()

        build(source_row(), source_resolver)

        self.assertEqual(source_resolver.calls, ["src:Source"])

    def test_blank_source_does_not_call_resolver(self):
        source_resolver = FakeSourceResolver()

        with self.assertRaisesRegex(
            WorkbookMappingError,
            "requires nonblank subject text",
        ):
            build(
                source_row(subject=" \t "),
                source_resolver,
            )

        self.assertEqual(source_resolver.calls, [])

    def test_unsupported_source_kind_is_rejected(self):
        source_resolver = FakeSourceResolver(
            ResolvedSourceEntity(
                SOURCE_CLASS,
                "unsupported",
            )
        )

        with self.assertRaisesRegex(
            WorkbookMappingError,
            "unsupported entity kind 'unsupported'",
        ):
            build(source_row(), source_resolver)

    def test_source_resolution_error_remains_distinct(self):
        error = EntityResolutionError("source lookup failed")

        with self.assertRaises(EntityResolutionError) as caught:
            build(
                source_row(),
                FakeSourceResolver(error=error),
            )

        self.assertIs(caught.exception, error)

    def test_parser_and_target_resolution_errors_remain_distinct(self):
        with self.assertRaises(MappingParseError):
            build(source_row(target="(ex:Class"))

        with self.assertRaises(EntityResolutionError):
            build(source_row(target="missing:Class"))

    def test_builder_compatibility_errors_remain_distinct(self):
        with self.assertRaises(MappingRecordBuildError):
            build(
                source_row(),
                property_source_resolver(),
            )

    def test_status_is_semantically_opaque(self):
        active = build(source_row(status="active"))
        other = build(source_row(status="anything-else"))

        self.assertEqual(active, other)
        self.assertFalse(hasattr(active, "status"))

    def test_row_id_is_copied_without_validation(self):
        record = build(
            source_row(row_id="not-a-canonical-row-id")
        )

        self.assertEqual(
            record.row_id,
            "not-a-canonical-row-id",
        )

    def test_location_does_not_change_record_or_enter_model(self):
        first_location = RowLocation("First", 2)
        second_location = RowLocation("Second", 99)
        first = build(source_row(location=first_location))
        second = build(source_row(location=second_location))

        self.assertEqual(first, second)
        self.assertFalse(hasattr(first, "location"))

        first_audit = build_row_audit(
            canonical_input_for_mapping_record(
                first,
                first_location,
            )
        )
        second_audit = build_row_audit(
            canonical_input_for_mapping_record(
                second,
                second_location,
            )
        )

        self.assertNotEqual(
            first_audit.location,
            second_audit.location,
        )
        self.assertEqual(
            first_audit.expression,
            second_audit.expression,
        )
        self.assertEqual(
            first_audit.source_expression_sha256,
            second_audit.source_expression_sha256,
        )
        self.assertEqual(
            first_audit.authoritative_axioms,
            second_audit.authoritative_axioms,
        )

    def test_complex_row_flows_through_identity_and_compiler(self):
        row = source_row(
            target=(
                "ex:Material and "
                "(ex:hasFunction some ex:SensingFunction)"
            ),
            reasoning="synthetic end-to-end mapping",
        )
        record = build(row)
        audit = build_row_audit(
            canonical_input_for_mapping_record(
                record,
                row.location,
            )
        )

        expected_axiom = (
            "SubClassOf(<urn:example:SourceClass> "
            "ObjectIntersectionOf(<urn:example:Material> "
            "ObjectSomeValuesFrom(<urn:example:hasFunction> "
            "<urn:example:SensingFunction>)))"
        )
        self.assertEqual(
            audit.authoritative_axioms[0].canonical_axiom,
            expected_axiom,
        )

        expected_turtle = (
            "<urn:example:SourceClass> "
            "<http://www.w3.org/2000/01/rdf-schema#subClassOf> "
            "[ <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> "
            "<http://www.w3.org/2002/07/owl#Class> ; "
            "<http://www.w3.org/2002/07/owl#intersectionOf> "
            "( <urn:example:Material> "
            "[ <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> "
            "<http://www.w3.org/2002/07/owl#Restriction> ; "
            "<http://www.w3.org/2002/07/owl#onProperty> "
            "<urn:example:hasFunction> ; "
            "<http://www.w3.org/2002/07/owl#someValuesFrom> "
            "<urn:example:SensingFunction> ] ) ] .\n"
        ).encode("utf-8")
        self.assertEqual(
            render_mapping_record_turtle(record),
            expected_turtle,
        )

    def test_implementation_dependencies_and_policy_are_neutral(self):
        path = Path("src/coms/workbook_mapping.py")
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        relative_imports = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.level
        }

        self.assertTrue(
            relative_imports.issubset(
                {
                    "adapters.xlsx",
                    "mapping_parser",
                    "mapping_predicates",
                    "mapping_record",
                    "mapping_record_builder",
                }
            )
        )
        self.assertNotIn("row_identity", relative_imports)
        self.assertIsNone(
            re.search(
                r"\b(?:SSN|SOSA|PROV|BFO|CCO|RO|HermiT)\b",
                source,
                flags=re.IGNORECASE,
            )
        )
        for forbidden in (
            "openpyxl",
            "rdflib",
            "mapping_compiler",
            "ontology_document",
            "publication",
            "release",
        ):
            self.assertNotIn(forbidden, source)

    def test_import_does_not_require_openpyxl(self):
        code = (
            "import builtins\n"
            "original = builtins.__import__\n"
            "def blocked(name, *args, **kwargs):\n"
            "    if name == 'openpyxl' or name.startswith('openpyxl.'):\n"
            "        raise ModuleNotFoundError(name)\n"
            "    return original(name, *args, **kwargs)\n"
            "builtins.__import__ = blocked\n"
            "import coms.workbook_mapping\n"
        )
        completed = subprocess.run(
            [sys.executable, "-c", code],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(
            completed.returncode,
            0,
            completed.stderr,
        )


if __name__ == "__main__":
    unittest.main()
