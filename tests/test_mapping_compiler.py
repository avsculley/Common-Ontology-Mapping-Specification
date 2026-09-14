import ast
from pathlib import Path
import re
import unittest

from coms.mapping_compiler import (
    MappingCompileError,
    render_mapping_record_turtle,
)
from coms.mapping_expression import (
    ExpressionNode,
)
from coms.mapping_parser import (
    ENTITY_CLASS,
    ENTITY_OBJECT_PROPERTY,
    EntityResolutionError,
)
from coms.mapping_predicates import (
    OWL_EQUIVALENT_CLASS,
    OWL_EQUIVALENT_PROPERTY,
    OWL_PROPERTY_CHAIN_AXIOM,
    RDFS_DOMAIN,
    RDFS_RANGE,
    RDFS_SUBCLASS_OF,
    RDFS_SUBPROPERTY_OF,
)
from coms.mapping_record import (
    GovernedMappingRecord,
)
from coms.mapping_record_builder import (
    build_governed_mapping_record,
)
from coms.row_identity import (
    RowLocation,
    build_row_audit,
    canonical_input_for_mapping_record,
)


ROW_ID = "urn:uuid:123e4567-e89b-42d3-a456-426614174000"
SOURCE_CLASS = "urn:example:SourceClass"
SOURCE_PROPERTY = "urn:example:source-property"
CLASS_A = "urn:example:A"
CLASS_B = "urn:example:B"
PROPERTY_1 = "urn:example:property-1"
PROPERTY_2 = "urn:example:property-2"

RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
OWL_CLASS = "http://www.w3.org/2002/07/owl#Class"
OWL_RESTRICTION = "http://www.w3.org/2002/07/owl#Restriction"
OWL_INTERSECTION_OF = "http://www.w3.org/2002/07/owl#intersectionOf"
OWL_UNION_OF = "http://www.w3.org/2002/07/owl#unionOf"
OWL_ON_PROPERTY = "http://www.w3.org/2002/07/owl#onProperty"
OWL_SOME_VALUES_FROM = "http://www.w3.org/2002/07/owl#someValuesFrom"


def iri(value: str) -> str:
    return f"<{value}>"


def named(value: str) -> ExpressionNode:
    return ExpressionNode(
        kind="named",
        iri=value,
    )


def intersection(*children: ExpressionNode) -> ExpressionNode:
    return ExpressionNode(
        kind="intersection",
        children=children,
    )


def union(*children: ExpressionNode) -> ExpressionNode:
    return ExpressionNode(
        kind="union",
        children=children,
    )


def some(
    property_iri: str,
    filler: ExpressionNode,
) -> ExpressionNode:
    return ExpressionNode(
        kind="some",
        property_iri=property_iri,
        filler=filler,
    )


def class_record(
    *,
    predicate_iri: str = RDFS_SUBCLASS_OF,
    expression: ExpressionNode | None = None,
    mapping_type: str = "class_mapping",
) -> GovernedMappingRecord:
    return GovernedMappingRecord(
        row_id=ROW_ID,
        subject_iri=SOURCE_CLASS,
        predicate_iri=predicate_iri,
        mapping_type=mapping_type,
        expression=expression or named(CLASS_A),
    )


def property_record(
    *,
    predicate_iri: str = RDFS_SUBPROPERTY_OF,
    target_property_iri: str | None = PROPERTY_1,
) -> GovernedMappingRecord:
    return GovernedMappingRecord(
        row_id=ROW_ID,
        subject_iri=SOURCE_PROPERTY,
        predicate_iri=predicate_iri,
        mapping_type="object_property_mapping",
        target_property_iri=target_property_iri,
    )


def restriction_turtle(
    property_iri: str,
    filler: str,
) -> str:
    return (
        f"[ {iri(RDF_TYPE)} {iri(OWL_RESTRICTION)} ; "
        f"{iri(OWL_ON_PROPERTY)} {iri(property_iri)} ; "
        f"{iri(OWL_SOME_VALUES_FROM)} {filler} ]"
    )


def boolean_turtle(
    predicate_iri: str,
    *operands: str,
) -> str:
    return (
        f"[ {iri(RDF_TYPE)} {iri(OWL_CLASS)} ; "
        f"{iri(predicate_iri)} ( {' '.join(operands)} ) ]"
    )


class DictResolver:
    def __init__(
        self,
        values: dict[tuple[str, str], str],
    ):
        self.values = values

    def resolve_entity(
        self,
        token: str,
        expected_kind: str,
    ) -> str:
        key = (
            token,
            expected_kind,
        )
        if key not in self.values:
            raise EntityResolutionError(
                f"cannot resolve {token!r} as {expected_kind}"
            )
        return self.values[key]


class MappingCompilerTests(unittest.TestCase):
    def assert_compilation(
        self,
        record: GovernedMappingRecord,
        turtle: str,
        canonical_axiom: str,
    ) -> None:
        self.assertEqual(
            render_mapping_record_turtle(record),
            turtle.encode("utf-8"),
        )
        audit = build_row_audit(
            canonical_input_for_mapping_record(
                record,
                RowLocation("Synthetic", 2),
            )
        )
        self.assertEqual(
            audit.authoritative_axioms[0].canonical_axiom,
            canonical_axiom,
        )

    def test_renders_named_subclass(self):
        self.assert_compilation(
            class_record(),
            (
                f"{iri(SOURCE_CLASS)} {iri(RDFS_SUBCLASS_OF)} "
                f"{iri(CLASS_A)} .\n"
            ),
            f"SubClassOf({iri(SOURCE_CLASS)} {iri(CLASS_A)})",
        )

    def test_renders_named_equivalent_class(self):
        self.assert_compilation(
            class_record(
                predicate_iri=OWL_EQUIVALENT_CLASS
            ),
            (
                f"{iri(SOURCE_CLASS)} {iri(OWL_EQUIVALENT_CLASS)} "
                f"{iri(CLASS_A)} .\n"
            ),
            f"EquivalentClasses({iri(SOURCE_CLASS)} {iri(CLASS_A)})",
        )

    def test_renders_object_subproperty(self):
        self.assert_compilation(
            property_record(),
            (
                f"{iri(SOURCE_PROPERTY)} {iri(RDFS_SUBPROPERTY_OF)} "
                f"{iri(PROPERTY_1)} .\n"
            ),
            (
                f"SubObjectPropertyOf("
                f"{iri(SOURCE_PROPERTY)} {iri(PROPERTY_1)})"
            ),
        )

    def test_renders_equivalent_object_property(self):
        self.assert_compilation(
            property_record(
                predicate_iri=OWL_EQUIVALENT_PROPERTY
            ),
            (
                f"{iri(SOURCE_PROPERTY)} {iri(OWL_EQUIVALENT_PROPERTY)} "
                f"{iri(PROPERTY_1)} .\n"
            ),
            (
                f"EquivalentObjectProperties("
                f"{iri(SOURCE_PROPERTY)} {iri(PROPERTY_1)})"
            ),
        )

    def test_renders_property_chain(self):
        record = GovernedMappingRecord(
            row_id=ROW_ID,
            subject_iri=SOURCE_PROPERTY,
            predicate_iri=OWL_PROPERTY_CHAIN_AXIOM,
            mapping_type="property_chain",
            property_chain=(
                PROPERTY_1,
                PROPERTY_2,
            ),
        )

        self.assert_compilation(
            record,
            (
                f"{iri(SOURCE_PROPERTY)} {iri(OWL_PROPERTY_CHAIN_AXIOM)} "
                f"( {iri(PROPERTY_1)} {iri(PROPERTY_2)} ) .\n"
            ),
            (
                "SubObjectPropertyOf("
                f"ObjectPropertyChain({iri(PROPERTY_1)} {iri(PROPERTY_2)}) "
                f"{iri(SOURCE_PROPERTY)})"
            ),
        )

    def test_renders_named_domain(self):
        record = GovernedMappingRecord(
            row_id=ROW_ID,
            subject_iri=SOURCE_PROPERTY,
            predicate_iri=RDFS_DOMAIN,
            mapping_type="domain",
            expression=named(CLASS_A),
        )

        self.assert_compilation(
            record,
            (
                f"{iri(SOURCE_PROPERTY)} {iri(RDFS_DOMAIN)} "
                f"{iri(CLASS_A)} .\n"
            ),
            f"ObjectPropertyDomain({iri(SOURCE_PROPERTY)} {iri(CLASS_A)})",
        )

    def test_renders_named_range(self):
        record = GovernedMappingRecord(
            row_id=ROW_ID,
            subject_iri=SOURCE_PROPERTY,
            predicate_iri=RDFS_RANGE,
            mapping_type="range",
            expression=named(CLASS_A),
        )

        self.assert_compilation(
            record,
            (
                f"{iri(SOURCE_PROPERTY)} {iri(RDFS_RANGE)} "
                f"{iri(CLASS_A)} .\n"
            ),
            f"ObjectPropertyRange({iri(SOURCE_PROPERTY)} {iri(CLASS_A)})",
        )

    def test_explicit_blank_renders_no_bytes(self):
        record = GovernedMappingRecord(
            row_id=ROW_ID,
            subject_iri=SOURCE_CLASS,
            predicate_iri=None,
            mapping_type="explicit_blank",
        )

        self.assertEqual(
            render_mapping_record_turtle(record),
            b"",
        )
        audit = build_row_audit(
            canonical_input_for_mapping_record(
                record,
                RowLocation("Synthetic", 2),
            )
        )
        self.assertEqual(
            audit.authoritative_axioms,
            (),
        )

    def test_renders_existential_target(self):
        target = some(
            PROPERTY_1,
            named(CLASS_A),
        )
        turtle_target = restriction_turtle(
            PROPERTY_1,
            iri(CLASS_A),
        )

        self.assert_compilation(
            class_record(expression=target),
            (
                f"{iri(SOURCE_CLASS)} {iri(RDFS_SUBCLASS_OF)} "
                f"{turtle_target} .\n"
            ),
            (
                f"SubClassOf({iri(SOURCE_CLASS)} "
                f"ObjectSomeValuesFrom({iri(PROPERTY_1)} {iri(CLASS_A)}))"
            ),
        )

    def test_renders_intersection_target(self):
        target = intersection(
            named(CLASS_B),
            named(CLASS_A),
        )
        turtle_target = boolean_turtle(
            OWL_INTERSECTION_OF,
            iri(CLASS_A),
            iri(CLASS_B),
        )

        self.assertEqual(
            render_mapping_record_turtle(
                class_record(expression=target)
            ),
            (
                f"{iri(SOURCE_CLASS)} {iri(RDFS_SUBCLASS_OF)} "
                f"{turtle_target} .\n"
            ).encode("utf-8"),
        )

    def test_renders_union_target(self):
        target = union(
            named(CLASS_B),
            named(CLASS_A),
        )
        turtle_target = boolean_turtle(
            OWL_UNION_OF,
            iri(CLASS_A),
            iri(CLASS_B),
        )

        self.assertEqual(
            render_mapping_record_turtle(
                class_record(expression=target)
            ),
            (
                f"{iri(SOURCE_CLASS)} {iri(RDFS_SUBCLASS_OF)} "
                f"{turtle_target} .\n"
            ).encode("utf-8"),
        )

    def test_renders_nested_intersection_and_existential(self):
        target = intersection(
            named(CLASS_A),
            some(
                PROPERTY_1,
                named(CLASS_B),
            ),
        )
        restriction = restriction_turtle(
            PROPERTY_1,
            iri(CLASS_B),
        )
        turtle_target = boolean_turtle(
            OWL_INTERSECTION_OF,
            iri(CLASS_A),
            restriction,
        )

        self.assert_compilation(
            class_record(expression=target),
            (
                f"{iri(SOURCE_CLASS)} {iri(RDFS_SUBCLASS_OF)} "
                f"{turtle_target} .\n"
            ),
            (
                f"SubClassOf({iri(SOURCE_CLASS)} "
                "ObjectIntersectionOf("
                f"{iri(CLASS_A)} "
                f"ObjectSomeValuesFrom({iri(PROPERTY_1)} {iri(CLASS_B)})))"
            ),
        )

    def test_intersection_operand_order_does_not_change_bytes(self):
        first = class_record(
            expression=intersection(
                named(CLASS_A),
                named(CLASS_B),
            )
        )
        second = class_record(
            expression=intersection(
                named(CLASS_B),
                named(CLASS_A),
            )
        )

        self.assertEqual(
            render_mapping_record_turtle(first),
            render_mapping_record_turtle(second),
        )

    def test_union_operand_order_does_not_change_bytes(self):
        first = class_record(
            expression=union(
                named(CLASS_A),
                named(CLASS_B),
            )
        )
        second = class_record(
            expression=union(
                named(CLASS_B),
                named(CLASS_A),
            )
        )

        self.assertEqual(
            render_mapping_record_turtle(first),
            render_mapping_record_turtle(second),
        )

    def test_nested_duplicate_boolean_operands_canonicalize_identically(self):
        cases = (
            (
                intersection(
                    named(CLASS_A),
                    intersection(
                        named(CLASS_B),
                        named(CLASS_A),
                    ),
                ),
                intersection(
                    named(CLASS_B),
                    named(CLASS_A),
                ),
            ),
            (
                union(
                    named(CLASS_A),
                    union(
                        named(CLASS_B),
                        named(CLASS_A),
                    ),
                ),
                union(
                    named(CLASS_B),
                    named(CLASS_A),
                ),
            ),
        )

        for nested, flat in cases:
            with self.subTest(kind=nested.kind):
                self.assertEqual(
                    render_mapping_record_turtle(
                        class_record(expression=nested)
                    ),
                    render_mapping_record_turtle(
                        class_record(expression=flat)
                    ),
                )

    def test_property_chain_order_remains_significant(self):
        first = GovernedMappingRecord(
            row_id=ROW_ID,
            subject_iri=SOURCE_PROPERTY,
            predicate_iri=OWL_PROPERTY_CHAIN_AXIOM,
            mapping_type="property_chain",
            property_chain=(PROPERTY_1, PROPERTY_2),
        )
        second = GovernedMappingRecord(
            row_id=ROW_ID,
            subject_iri=SOURCE_PROPERTY,
            predicate_iri=OWL_PROPERTY_CHAIN_AXIOM,
            mapping_type="property_chain",
            property_chain=(PROPERTY_2, PROPERTY_1),
        )

        self.assertNotEqual(
            render_mapping_record_turtle(first),
            render_mapping_record_turtle(second),
        )

    def test_rejects_malformed_and_incompatible_records(self):
        cases = (
            GovernedMappingRecord(
                row_id=ROW_ID,
                subject_iri=SOURCE_CLASS,
                predicate_iri=RDFS_SUBCLASS_OF,
                mapping_type="unsupported",
                expression=named(CLASS_A),
            ),
            class_record(
                predicate_iri=RDFS_DOMAIN
            ),
            GovernedMappingRecord(
                row_id=ROW_ID,
                subject_iri=SOURCE_CLASS,
                predicate_iri=RDFS_SUBCLASS_OF,
                mapping_type="class_mapping",
            ),
            property_record(
                target_property_iri=None
            ),
            GovernedMappingRecord(
                row_id=ROW_ID,
                subject_iri=SOURCE_PROPERTY,
                predicate_iri=OWL_PROPERTY_CHAIN_AXIOM,
                mapping_type="property_chain",
            ),
            GovernedMappingRecord(
                row_id=ROW_ID,
                subject_iri=SOURCE_PROPERTY,
                predicate_iri=OWL_PROPERTY_CHAIN_AXIOM,
                mapping_type="property_chain",
                property_chain=(PROPERTY_1,),
            ),
            GovernedMappingRecord(
                row_id=ROW_ID,
                subject_iri=SOURCE_CLASS,
                predicate_iri=RDFS_SUBCLASS_OF,
                mapping_type="explicit_blank",
            ),
            GovernedMappingRecord(
                row_id=ROW_ID,
                subject_iri=SOURCE_CLASS,
                predicate_iri=None,
                mapping_type="explicit_blank",
                expression=named(CLASS_A),
            ),
        )

        for record in cases:
            with self.subTest(
                mapping_type=record.mapping_type,
                predicate_iri=record.predicate_iri,
            ):
                with self.assertRaises(MappingCompileError):
                    render_mapping_record_turtle(record)

    def test_rejects_unsupported_expression(self):
        with self.assertRaisesRegex(
            MappingCompileError,
            "unsupported expression node kind",
        ):
            render_mapping_record_turtle(
                class_record(
                    expression=ExpressionNode(
                        kind="unsupported"
                    )
                )
            )

    def test_rejects_incomplete_existential_restriction(self):
        with self.assertRaisesRegex(
            MappingCompileError,
            "existential restriction lacks",
        ):
            render_mapping_record_turtle(
                class_record(
                    expression=ExpressionNode(
                        kind="some",
                        property_iri=PROPERTY_1,
                    )
                )
            )

    def test_rejects_empty_required_iris(self):
        cases = (
            class_record(),
            class_record(
                expression=named("")
            ),
            property_record(
                target_property_iri=""
            ),
            GovernedMappingRecord(
                row_id=ROW_ID,
                subject_iri=SOURCE_PROPERTY,
                predicate_iri=OWL_PROPERTY_CHAIN_AXIOM,
                mapping_type="property_chain",
                property_chain=(PROPERTY_1, ""),
            ),
        )
        cases = (
            GovernedMappingRecord(
                row_id=record.row_id,
                subject_iri=(
                    ""
                    if index == 0
                    else record.subject_iri
                ),
                predicate_iri=record.predicate_iri,
                mapping_type=record.mapping_type,
                reasoning=record.reasoning,
                expression=record.expression,
                target_property_iri=record.target_property_iri,
                property_chain=record.property_chain,
            )
            for index, record in enumerate(cases)
        )

        for record in cases:
            with self.subTest(mapping_type=record.mapping_type):
                with self.assertRaisesRegex(
                    MappingCompileError,
                    "nonempty",
                ):
                    render_mapping_record_turtle(record)

    def test_active_output_is_one_statement_with_exactly_one_final_lf(self):
        records = (
            class_record(),
            property_record(),
            GovernedMappingRecord(
                row_id=ROW_ID,
                subject_iri=SOURCE_PROPERTY,
                predicate_iri=OWL_PROPERTY_CHAIN_AXIOM,
                mapping_type="property_chain",
                property_chain=(PROPERTY_1, PROPERTY_2),
            ),
        )

        for record in records:
            with self.subTest(mapping_type=record.mapping_type):
                rendered = render_mapping_record_turtle(record)
                self.assertTrue(rendered.endswith(b".\n"))
                self.assertEqual(rendered.count(b"\n"), 1)
                self.assertNotIn(b"@prefix", rendered)
                self.assertNotIn(b"PREFIX", rendered)

    def test_compiler_dependencies_and_policy_are_neutral(self):
        path = Path("src/coms/mapping_compiler.py")
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        classes = [
            node.name
            for node in tree.body
            if isinstance(node, ast.ClassDef)
        ]

        self.assertEqual(
            classes,
            ["MappingCompileError"],
        )
        for value in (
            "row_identity",
            "mapping_parser",
            "mapping_record_builder",
            "configuration",
            "publication",
            "release_context",
            "openpyxl",
            "rdflib",
            "Workbook",
            "Worksheet",
            "URIRef",
            "Graph",
        ):
            self.assertNotIn(value, source)

        project_pattern = re.compile(
            r"\b(?:SSN|SOSA|PROV|BFO|CCO|RO|HermiT)\b",
            re.IGNORECASE,
        )
        self.assertIsNone(project_pattern.search(source))

    def test_text_to_record_to_turtle_end_to_end(self):
        entity_resolver = DictResolver(
            {
                ("ex:Material", ENTITY_CLASS): "urn:example:Material",
                ("ex:hasFunction", ENTITY_OBJECT_PROPERTY): (
                    "urn:example:hasFunction"
                ),
                ("ex:SensingFunction", ENTITY_CLASS): (
                    "urn:example:SensingFunction"
                ),
            }
        )
        record = build_governed_mapping_record(
            row_id=ROW_ID,
            subject_iri=SOURCE_CLASS,
            subject_kind=ENTITY_CLASS,
            predicate_iri=RDFS_SUBCLASS_OF,
            target_text=(
                "ex:Material and "
                "(ex:hasFunction some ex:SensingFunction)"
            ),
            resolver=entity_resolver,
            reasoning="synthetic compiler integration",
        )
        restriction = restriction_turtle(
            "urn:example:hasFunction",
            iri("urn:example:SensingFunction"),
        )
        turtle_target = boolean_turtle(
            OWL_INTERSECTION_OF,
            iri("urn:example:Material"),
            restriction,
        )

        self.assert_compilation(
            record,
            (
                f"{iri(SOURCE_CLASS)} {iri(RDFS_SUBCLASS_OF)} "
                f"{turtle_target} .\n"
            ),
            (
                f"SubClassOf({iri(SOURCE_CLASS)} "
                "ObjectIntersectionOf("
                f"{iri('urn:example:Material')} "
                "ObjectSomeValuesFrom("
                f"{iri('urn:example:hasFunction')} "
                f"{iri('urn:example:SensingFunction')})))"
            ),
        )
