import ast
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
import re
import subprocess
import sys
import unittest

from coms.adapters.xlsx import WorkbookSourceRow
from coms.mapping_expression import ExpressionNode
from coms.mapping_parser import (
    ENTITY_CLASS,
    ENTITY_OBJECT_PROPERTY,
    EntityResolutionError,
)
from coms.mapping_predicates import (
    OWL_PROPERTY_CHAIN_AXIOM,
    RDFS_SUBCLASS_OF,
    RDFS_SUBPROPERTY_OF,
)
from coms.mapping_record import GovernedMappingRecord
from coms.row_identity import (
    ComsRowIdentityError,
    RowLocation,
)
from coms.workbook_batch import (
    AuditedWorkbookRow,
    build_governed_workbook_batch,
    validate_workbook_source_row_ids,
)
from coms.workbook_mapping import ResolvedSourceEntity


ROW_ID_1 = "urn:uuid:123e4567-e89b-42d3-a456-426614174000"
ROW_ID_2 = "urn:uuid:123e4567-e89b-42d3-b456-426614174001"
ROW_ID_3 = "urn:uuid:123e4567-e89b-42d3-8456-426614174002"
ROW_ID_4 = "urn:uuid:123e4567-e89b-42d3-9456-426614174003"

SOURCE_CLASS = "urn:example:SourceClass"
SOURCE_PROPERTY = "urn:example:source-property"
SECOND_SOURCE_PROPERTY = "urn:example:second-source-property"
TARGET_CLASS = "urn:example:TargetClass"
SECOND_TARGET_CLASS = "urn:example:SecondTargetClass"
TARGET_PROPERTY = "urn:example:target-property"
FIRST_PROPERTY = "urn:example:first-property"
SECOND_PROPERTY = "urn:example:second-property"
MATERIAL = "urn:example:Material"
HAS_FUNCTION = "urn:example:hasFunction"
SENSING_FUNCTION = "urn:example:SensingFunction"


class SingleUseIterable:
    def __init__(self, values):
        self.values = tuple(values)
        self.iterations = 0

    def __iter__(self):
        self.iterations += 1

        if self.iterations > 1:
            raise AssertionError(
                "source iterable was consumed more than once"
            )

        return iter(self.values)


class FakeSourceResolver:
    def __init__(self, *, errors=None):
        self.values = {
            "src:Class": ResolvedSourceEntity(
                SOURCE_CLASS,
                ENTITY_CLASS,
            ),
            "src:Property": ResolvedSourceEntity(
                SOURCE_PROPERTY,
                ENTITY_OBJECT_PROPERTY,
            ),
            "src:SecondProperty": ResolvedSourceEntity(
                SECOND_SOURCE_PROPERTY,
                ENTITY_OBJECT_PROPERTY,
            ),
        }
        self.errors = errors or {}
        self.calls = []

    def resolve_source_entity(self, token):
        self.calls.append(token)

        if token in self.errors:
            raise self.errors[token]

        return self.values[token]


class FakeTargetResolver:
    def __init__(self):
        self.values = {
            ("ex:Class", ENTITY_CLASS): TARGET_CLASS,
            ("ex:SecondClass", ENTITY_CLASS): SECOND_TARGET_CLASS,
            ("ex:property", ENTITY_OBJECT_PROPERTY): TARGET_PROPERTY,
            ("ex:first", ENTITY_OBJECT_PROPERTY): FIRST_PROPERTY,
            ("ex:second", ENTITY_OBJECT_PROPERTY): SECOND_PROPERTY,
            ("ex:Material", ENTITY_CLASS): MATERIAL,
            ("ex:hasFunction", ENTITY_OBJECT_PROPERTY): HAS_FUNCTION,
            ("ex:SensingFunction", ENTITY_CLASS): SENSING_FUNCTION,
        }
        self.calls = []

    def resolve_entity(self, token, expected_kind):
        self.calls.append(
            (token, expected_kind)
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


def source_row(
    *,
    row_id=ROW_ID_1,
    row_number=2,
    subject="src:Class",
    predicate="rdfs:subClassOf",
    target="ex:Class",
    reasoning="because",
    status=None,
    worksheet="Mappings",
):
    return WorkbookSourceRow(
        location=RowLocation(
            worksheet,
            row_number,
        ),
        row_id_text=row_id,
        subject_text=subject,
        predicate_text=predicate,
        target_text=target,
        reasoning_text=reasoning,
        status_text=status,
    )


def build(rows, source_resolver=None, target_resolver=None):
    return build_governed_workbook_batch(
        rows,
        source_resolver or FakeSourceResolver(),
        target_resolver or FakeTargetResolver(),
    )


class WorkbookBatchTests(unittest.TestCase):
    def test_audited_workbook_row_is_frozen(self):
        item = build((source_row(),))[0]

        with self.assertRaises(FrozenInstanceError):
            item.governed_record = item.governed_record

    def test_row_id_preflight_materializes_input_once(self):
        rows = SingleUseIterable(
            (
                source_row(),
                source_row(
                    row_id=ROW_ID_2,
                    row_number=3,
                    target="ex:SecondClass",
                ),
            )
        )

        validate_workbook_source_row_ids(rows)

        self.assertEqual(rows.iterations, 1)

    def test_batch_materializes_input_once(self):
        rows = SingleUseIterable(
            (
                source_row(),
                source_row(
                    row_id=ROW_ID_2,
                    row_number=3,
                    target="ex:SecondClass",
                ),
            )
        )

        result = build(rows)

        self.assertEqual(rows.iterations, 1)
        self.assertEqual(len(result), 2)

    def test_successful_results_preserve_caller_order(self):
        rows = (
            source_row(
                row_id=ROW_ID_2,
                row_number=9,
                subject="src:Property",
                predicate="rdfs:subPropertyOf",
                target="ex:property",
            ),
            source_row(
                row_id=ROW_ID_1,
                row_number=2,
            ),
        )

        result = build(rows)

        self.assertEqual(
            tuple(item.source_row for item in result),
            rows,
        )
        self.assertEqual(
            tuple(item.governed_record.row_id for item in result),
            (ROW_ID_2, ROW_ID_1),
        )

    def test_reuses_same_resolver_instances_for_all_rows(self):
        source_resolver = FakeSourceResolver()
        target_resolver = FakeTargetResolver()
        rows = (
            source_row(),
            source_row(
                row_id=ROW_ID_2,
                row_number=3,
                subject="src:Property",
                predicate="rdfs:subPropertyOf",
                target="ex:property",
            ),
        )

        build(
            rows,
            source_resolver,
            target_resolver,
        )

        self.assertEqual(
            source_resolver.calls,
            ["src:Class", "src:Property"],
        )
        self.assertEqual(
            target_resolver.calls,
            [
                ("ex:Class", ENTITY_CLASS),
                ("ex:property", ENTITY_OBJECT_PROPERTY),
            ],
        )

    def test_invalid_row_ids_fail_before_source_resolution(self):
        source_resolver = FakeSourceResolver()

        with self.assertRaises(ComsRowIdentityError):
            build(
                (
                    source_row(),
                    source_row(
                        row_id="invalid",
                        row_number=3,
                    ),
                ),
                source_resolver,
            )

        self.assertEqual(source_resolver.calls, [])

    def test_duplicate_row_ids_fail_before_source_resolution(self):
        source_resolver = FakeSourceResolver()

        with self.assertRaises(ComsRowIdentityError) as caught:
            build(
                (
                    source_row(),
                    source_row(
                        row_number=3,
                    ),
                ),
                source_resolver,
            )

        self.assertEqual(source_resolver.calls, [])
        self.assertEqual(
            caught.exception.issues[0].code,
            "DUPLICATE_ROW_ID",
        )

    def test_multiple_invalid_row_ids_accumulate_deterministically(self):
        rows = (
            source_row(
                row_id="",
                row_number=9,
            ),
            source_row(
                row_id="not-canonical",
                row_number=3,
            ),
            source_row(
                row_id="",
                row_number=6,
            ),
        )

        with self.assertRaises(ComsRowIdentityError) as caught:
            validate_workbook_source_row_ids(rows)

        self.assertEqual(
            tuple(issue.location.row_number for issue in caught.exception.issues),
            (3, 6, 9),
        )
        self.assertEqual(
            tuple(issue.code for issue in caught.exception.issues),
            (
                "MALFORMED_ROW_ID",
                "MISSING_ROW_ID",
                "MISSING_ROW_ID",
            ),
        )

    def test_selected_batch_rechecks_row_ids(self):
        validate_workbook_source_row_ids(
            (source_row(),)
        )
        source_resolver = FakeSourceResolver()
        selected = (
            source_row(
                row_id="changed-after-selection",
            ),
        )

        with self.assertRaises(ComsRowIdentityError):
            build(
                selected,
                source_resolver,
            )

        self.assertEqual(source_resolver.calls, [])

    def test_full_preflight_includes_rows_later_excluded(self):
        full_rows = (
            source_row(
                status="selected",
            ),
            source_row(
                row_number=3,
                status="excluded",
            ),
        )

        with self.assertRaises(ComsRowIdentityError):
            validate_workbook_source_row_ids(
                full_rows
            )

        selected = tuple(
            row
            for row in full_rows
            if row.status_text == "selected"
        )
        self.assertEqual(len(build(selected)), 1)

    def test_semantic_failure_is_fail_fast_without_partial_result(self):
        error = EntityResolutionError(
            "source lookup failed"
        )
        source_resolver = FakeSourceResolver(
            errors={"src:Property": error}
        )
        target_resolver = FakeTargetResolver()
        rows = (
            source_row(),
            source_row(
                row_id=ROW_ID_2,
                row_number=3,
                subject="src:Property",
            ),
            source_row(
                row_id=ROW_ID_3,
                row_number=4,
                subject="src:SecondProperty",
            ),
        )

        with self.assertRaises(EntityResolutionError):
            build(
                rows,
                source_resolver,
                target_resolver,
            )

        self.assertEqual(
            source_resolver.calls,
            ["src:Class", "src:Property"],
        )
        self.assertEqual(
            target_resolver.calls,
            [("ex:Class", ENTITY_CLASS)],
        )

    def test_semantic_exception_type_and_message_are_preserved(self):
        error = EntityResolutionError(
            "source lookup failed"
        )

        with self.assertRaises(EntityResolutionError) as caught:
            build(
                (source_row(),),
                FakeSourceResolver(
                    errors={"src:Class": error}
                ),
            )

        self.assertIs(caught.exception, error)
        self.assertEqual(
            str(caught.exception),
            "source lookup failed",
        )

    def test_semantic_exception_has_row_diagnostic_note(self):
        error = EntityResolutionError(
            "source lookup failed"
        )

        with self.assertRaises(EntityResolutionError) as caught:
            build(
                (source_row(),),
                FakeSourceResolver(
                    errors={"src:Class": error}
                ),
            )

        self.assertEqual(
            caught.exception.__notes__,
            [
                "Workbook source row: "
                f"Mappings!2 [{ROW_ID_1}]"
            ],
        )

    def test_equivalent_diagnostic_note_is_not_duplicated(self):
        error = EntityResolutionError(
            "source lookup failed"
        )
        source_resolver = FakeSourceResolver(
            errors={"src:Class": error}
        )

        for _ in range(2):
            with self.assertRaises(EntityResolutionError):
                build(
                    (source_row(),),
                    source_resolver,
                )

        self.assertEqual(
            len(error.__notes__),
            1,
        )

    def test_explicit_blank_has_zero_authoritative_axioms(self):
        item = build(
            (
                source_row(
                    predicate="",
                    target="",
                ),
            )
        )[0]

        self.assertEqual(
            item.governed_record.mapping_type,
            "explicit_blank",
        )
        self.assertEqual(
            item.row_audit.authoritative_axioms,
            (),
        )

    def test_duplicate_authoritative_axioms_fail_after_all_rows_audit(self):
        source_resolver = FakeSourceResolver()
        target_resolver = FakeTargetResolver()
        rows = (
            source_row(),
            source_row(
                row_id=ROW_ID_2,
                row_number=3,
                reasoning="different metadata",
            ),
        )

        with self.assertRaises(ComsRowIdentityError) as caught:
            build(
                rows,
                source_resolver,
                target_resolver,
            )

        self.assertEqual(
            source_resolver.calls,
            ["src:Class", "src:Class"],
        )
        self.assertEqual(
            target_resolver.calls,
            [
                ("ex:Class", ENTITY_CLASS),
                ("ex:Class", ENTITY_CLASS),
            ],
        )
        issue = caught.exception.issues[0]
        self.assertEqual(
            issue.code,
            "DUPLICATE_AUTHORITATIVE_AXIOM",
        )
        self.assertEqual(
            issue.location,
            RowLocation("Mappings", 3),
        )
        self.assertIn(ROW_ID_1, issue.message)
        self.assertIn("Mappings!2", issue.message)

    def test_same_subject_predicate_with_different_targets_is_allowed(self):
        result = build(
            (
                source_row(),
                source_row(
                    row_id=ROW_ID_2,
                    row_number=3,
                    target="ex:SecondClass",
                ),
            )
        )

        self.assertEqual(len(result), 2)
        self.assertNotEqual(
            result[0].row_audit.authoritative_axioms,
            result[1].row_audit.authoritative_axioms,
        )

    def test_location_remains_associated_but_outside_semantic_record(self):
        location = RowLocation(
            "Second sheet",
            27,
        )
        item = build(
            (
                source_row(
                    worksheet=location.worksheet,
                    row_number=location.row_number,
                ),
            )
        )[0]

        self.assertEqual(
            item.source_row.location,
            location,
        )
        self.assertEqual(
            item.row_audit.location,
            location,
        )
        self.assertFalse(
            hasattr(
                item.governed_record,
                "location",
            )
        )

    def test_status_text_is_semantically_opaque(self):
        first = build(
            (source_row(status="first-state"),)
        )[0]
        second = build(
            (source_row(status="second-state"),)
        )[0]

        self.assertEqual(
            first.governed_record,
            second.governed_record,
        )
        self.assertEqual(
            first.row_audit,
            second.row_audit,
        )

    def test_import_does_not_require_openpyxl_or_rdflib(self):
        code = (
            "import builtins\n"
            "original = builtins.__import__\n"
            "def blocked(name, *args, **kwargs):\n"
            "    if name in {'openpyxl', 'rdflib'} or "
            "name.startswith(('openpyxl.', 'rdflib.')):\n"
            "        raise ModuleNotFoundError(name)\n"
            "    return original(name, *args, **kwargs)\n"
            "builtins.__import__ = blocked\n"
            "import coms.workbook_batch\n"
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

    def test_implementation_dependencies_and_policy_are_neutral(self):
        path = Path(
            "src/coms/workbook_batch.py"
        )
        source = path.read_text(
            encoding="utf-8"
        )
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
                    "mapping_record",
                    "row_identity",
                    "workbook_mapping",
                }
            )
        )
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
            "ProductDefinition",
            "release",
        ):
            self.assertNotIn(forbidden, source)

    def test_end_to_end_batch_preserves_all_associations(self):
        rows = (
            source_row(
                target=(
                    "ex:Material and "
                    "(ex:hasFunction some ex:SensingFunction)"
                ),
            ),
            source_row(
                row_id=ROW_ID_2,
                row_number=3,
                subject="src:Property",
                predicate="rdfs:subPropertyOf",
                target="ex:property",
            ),
            source_row(
                row_id=ROW_ID_3,
                row_number=4,
                subject="src:SecondProperty",
                predicate="owl:propertyChainAxiom",
                target="ex:first o ex:second",
            ),
            source_row(
                row_id=ROW_ID_4,
                row_number=5,
                predicate="",
                target="",
            ),
        )

        result = build(rows)

        self.assertEqual(
            tuple(item.source_row for item in result),
            rows,
        )
        self.assertEqual(
            result[0].governed_record,
            GovernedMappingRecord(
                row_id=ROW_ID_1,
                subject_iri=SOURCE_CLASS,
                predicate_iri=RDFS_SUBCLASS_OF,
                mapping_type="class_mapping",
                reasoning="because",
                expression=ExpressionNode(
                    kind="intersection",
                    children=(
                        ExpressionNode(
                            kind="named",
                            iri=MATERIAL,
                        ),
                        ExpressionNode(
                            kind="some",
                            property_iri=HAS_FUNCTION,
                            filler=ExpressionNode(
                                kind="named",
                                iri=SENSING_FUNCTION,
                            ),
                        ),
                    ),
                ),
            ),
        )
        self.assertEqual(
            result[1].governed_record,
            GovernedMappingRecord(
                row_id=ROW_ID_2,
                subject_iri=SOURCE_PROPERTY,
                predicate_iri=RDFS_SUBPROPERTY_OF,
                mapping_type="object_property_mapping",
                reasoning="because",
                target_property_iri=TARGET_PROPERTY,
            ),
        )
        self.assertEqual(
            result[2].governed_record,
            GovernedMappingRecord(
                row_id=ROW_ID_3,
                subject_iri=SECOND_SOURCE_PROPERTY,
                predicate_iri=OWL_PROPERTY_CHAIN_AXIOM,
                mapping_type="property_chain",
                reasoning="because",
                property_chain=(
                    FIRST_PROPERTY,
                    SECOND_PROPERTY,
                ),
            ),
        )
        self.assertEqual(
            result[3].governed_record.mapping_type,
            "explicit_blank",
        )
        self.assertEqual(
            sum(
                len(item.row_audit.authoritative_axioms)
                for item in result
            ),
            3,
        )
        self.assertEqual(
            result[3].row_audit.authoritative_axioms,
            (),
        )


if __name__ == "__main__":
    unittest.main()
