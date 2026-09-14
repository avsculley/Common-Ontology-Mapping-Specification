import ast
from dataclasses import replace
from pathlib import Path
import re
import unittest
from unittest.mock import patch

from coms.config.model import (
    ExpressionProfile,
    ProductDefinition,
    ProductGraph,
    ProductImport,
    ProjectConfig,
    PublicationAnnotationRule,
    PublicationProfile,
    ReleaseLayout,
    WorkbookProfile,
)
from coms.mapping_compiler import (
    MappingCompileError,
    render_mapping_record_turtle,
)
from coms.mapping_expression import ExpressionNode
from coms.mapping_parser import (
    ENTITY_CLASS,
    ENTITY_OBJECT_PROPERTY,
    EntityResolutionError,
)
from coms.mapping_predicates import (
    OWL_PROPERTY_CHAIN_AXIOM,
    RDFS_SUBCLASS_OF,
)
from coms.mapping_record import GovernedMappingRecord
from coms.mapping_record_builder import build_governed_mapping_record
from coms.ontology_document import (
    OntologyDocumentError,
    render_ontology_document,
)
from coms.publication import (
    PublicationError,
    render_ontology_header_bytes,
)
from coms.release_context import FormalReleaseContext
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


def named(iri: str) -> ExpressionNode:
    return ExpressionNode(
        kind="named",
        iri=iri,
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


def intersection(
    *children: ExpressionNode,
) -> ExpressionNode:
    return ExpressionNode(
        kind="intersection",
        children=children,
    )


def class_record(
    *,
    subject_iri: str = SOURCE_CLASS,
    expression: ExpressionNode | None = None,
    row_id: str = ROW_ID,
) -> GovernedMappingRecord:
    return GovernedMappingRecord(
        row_id=row_id,
        subject_iri=subject_iri,
        predicate_iri=RDFS_SUBCLASS_OF,
        mapping_type="class_mapping",
        expression=expression or named(CLASS_A),
    )


def blank_record() -> GovernedMappingRecord:
    return GovernedMappingRecord(
        row_id=ROW_ID,
        subject_iri=SOURCE_CLASS,
        predicate_iri=None,
        mapping_type="explicit_blank",
    )


def chain_record() -> GovernedMappingRecord:
    return GovernedMappingRecord(
        row_id=ROW_ID,
        subject_iri=SOURCE_PROPERTY,
        predicate_iri=OWL_PROPERTY_CHAIN_AXIOM,
        mapping_type="property_chain",
        property_chain=(
            PROPERTY_2,
            PROPERTY_1,
            PROPERTY_2,
        ),
    )


def project_config() -> ProjectConfig:
    base = ProductDefinition(
        product_key="base",
        output_path="build/base.ttl",
        product_type="ontology",
        stable_ontology_iri="urn:example:ontology:base",
        release_iri_pattern=(
            "urn:example:release:"
            "{release_identifier}:base"
        ),
    )
    document = ProductDefinition(
        product_key="document",
        output_path="build/document.ttl",
        product_type="mapping",
        stable_ontology_iri=(
            "urn:example:ontology:document"
        ),
        release_iri_pattern=(
            "urn:example:release:"
            "{release_identifier}:document"
        ),
        product_imports=(
            ProductImport(
                product_key="base",
                formal_target="release",
            ),
        ),
    )
    return ProjectConfig(
        project_key="synthetic",
        project_title="Synthetic Mapping",
        repository_root=".",
        authoritative_mapping_source="source",
        primary_output="document",
        generated_warning="GENERATED FILE",
        configuration_schema_version="1",
        workbook=WorkbookProfile(
            workbook_path="mapping.xlsx",
            row_id_column="RowID",
        ),
        vocabularies=(),
        expressions=ExpressionProfile(),
        product_graph=ProductGraph(
            products=(
                base,
                document,
            ),
        ),
        validation_profiles=(),
        publication=PublicationProfile(
            project_title="Synthetic Mapping",
            annotation_rules=(
                PublicationAnnotationRule(
                    predicate_iri="urn:example:label",
                    object_kind="plain_literal",
                    fixed_value="Synthetic ontology",
                ),
                PublicationAnnotationRule(
                    predicate_iri="urn:example:version",
                    object_kind="iri",
                    applicability="formal",
                    value_source=(
                        "product.release_version_iri"
                    ),
                ),
            ),
        ),
        release_layout=ReleaseLayout(),
    )


def formal_context() -> FormalReleaseContext:
    return FormalReleaseContext(
        release_identifier="2099-01-02",
        release_date="2099-01-02",
        git_tag="v2099-01-02",
        source_commit=(
            "0123456789abcdef"
            "0123456789abcdef"
            "01234567"
        ),
    )


class DictResolver:
    def __init__(
        self,
        values: dict[tuple[str, str], str],
    ) -> None:
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


class OntologyDocumentTests(unittest.TestCase):
    def test_one_active_mapping_follows_publication_header(self):
        config = project_config()
        record = class_record()
        header = render_ontology_header_bytes(
            config,
            "document",
        )
        statement = render_mapping_record_turtle(
            record
        )

        self.assertEqual(
            render_ontology_document(
                config,
                "document",
                (record,),
            ),
            header + statement,
        )

    def test_multiple_active_mappings_are_sorted_by_compiled_bytes(self):
        config = project_config()
        records = (
            class_record(
                subject_iri="urn:example:Z",
                expression=named(CLASS_B),
            ),
            chain_record(),
            class_record(
                subject_iri="urn:example:A",
            ),
        )
        header = render_ontology_header_bytes(
            config,
            "document",
        )
        statements = sorted(
            render_mapping_record_turtle(record)
            for record in records
        )

        self.assertEqual(
            render_ontology_document(
                config,
                "document",
                records,
            ),
            header + b"".join(statements),
        )

    def test_reversed_input_order_produces_identical_bytes(self):
        config = project_config()
        records = (
            class_record(
                subject_iri="urn:example:Z",
            ),
            chain_record(),
            class_record(
                subject_iri="urn:example:A",
            ),
        )

        self.assertEqual(
            render_ontology_document(
                config,
                "document",
                records,
            ),
            render_ontology_document(
                config,
                "document",
                reversed(records),
            ),
        )

    def test_explicit_blank_is_omitted_from_body(self):
        config = project_config()
        active = class_record()

        self.assertEqual(
            render_ontology_document(
                config,
                "document",
                (
                    blank_record(),
                    active,
                ),
            ),
            render_ontology_document(
                config,
                "document",
                (active,),
            ),
        )

    def test_all_explicit_blanks_produce_exact_header(self):
        config = project_config()

        self.assertEqual(
            render_ontology_document(
                config,
                "document",
                (
                    blank_record(),
                    blank_record(),
                ),
            ),
            render_ontology_header_bytes(
                config,
                "document",
            ),
        )

    def test_duplicate_active_statements_are_rejected(self):
        config = project_config()
        first = class_record()
        duplicate = replace(
            first,
            row_id=(
                "urn:uuid:123e4567-e89b-"
                "42d3-a456-426614174001"
            ),
            reasoning="different source metadata",
        )
        statement = render_mapping_record_turtle(
            first
        )

        with self.assertRaises(
            OntologyDocumentError
        ) as context:
            render_ontology_document(
                config,
                "document",
                (
                    first,
                    duplicate,
                ),
            )

        self.assertEqual(
            context.exception.duplicate_statement,
            statement,
        )

    def test_nested_expression_serialization_survives_composition(self):
        config = project_config()
        record = class_record(
            expression=intersection(
                some(
                    PROPERTY_1,
                    named(CLASS_B),
                ),
                named(CLASS_A),
                intersection(
                    named(CLASS_B),
                    named(CLASS_A),
                ),
            )
        )

        self.assertEqual(
            render_ontology_document(
                config,
                "document",
                (record,),
            ),
            (
                render_ontology_header_bytes(
                    config,
                    "document",
                )
                + render_mapping_record_turtle(
                    record
                )
            ),
        )

    def test_property_chain_statement_remains_intact(self):
        config = project_config()
        record = chain_record()
        statement = render_mapping_record_turtle(
            record
        )
        document = render_ontology_document(
            config,
            "document",
            (record,),
        )

        self.assertTrue(
            document.endswith(statement)
        )
        self.assertIn(
            (
                b"( <urn:example:property-2> "
                b"<urn:example:property-1> "
                b"<urn:example:property-2> )"
            ),
            document,
        )

    def test_complete_document_has_exactly_one_final_lf(self):
        document = render_ontology_document(
            project_config(),
            "document",
            (
                class_record(),
                chain_record(),
            ),
        )

        self.assertTrue(
            document.endswith(b".\n")
        )
        self.assertFalse(
            document.endswith(b"\n\n")
        )

    def test_existing_header_renderer_output_is_used_unchanged(self):
        config = project_config()
        record = class_record()
        header = render_ontology_header_bytes(
            config,
            "document",
        )
        document = render_ontology_document(
            config,
            "document",
            (record,),
        )

        self.assertEqual(
            document[:len(header)],
            header,
        )
        self.assertEqual(
            document[len(header):],
            render_mapping_record_turtle(record),
        )

    def test_header_authority_is_called_with_the_existing_api(self):
        config = project_config()
        context = formal_context()
        header = b"<urn:example:ontology> <urn:example:p> <urn:example:o> .\n"

        with patch(
            "coms.ontology_document.render_ontology_header_bytes",
            return_value=header,
        ) as renderer:
            observed = render_ontology_document(
                config,
                "document",
                (),
                context,
            )

        self.assertEqual(observed, header)
        renderer.assert_called_once_with(
            config,
            "document",
            context,
        )

    def test_repeated_equal_inputs_produce_identical_bytes(self):
        config = project_config()
        records = (
            class_record(),
            chain_record(),
        )

        first = render_ontology_document(
            config,
            "document",
            iter(records),
        )
        second = render_ontology_document(
            config,
            "document",
            iter(records),
        )

        self.assertEqual(first, second)

    def test_development_and_formal_headers_are_preserved(self):
        config = project_config()
        record = class_record()
        statement = render_mapping_record_turtle(
            record
        )
        development_header = render_ontology_header_bytes(
            config,
            "document",
        )
        formal_header = render_ontology_header_bytes(
            config,
            "document",
            formal_context(),
        )
        development = render_ontology_document(
            config,
            "document",
            (record,),
        )
        formal = render_ontology_document(
            config,
            "document",
            (record,),
            formal_context(),
        )

        self.assertEqual(
            development,
            development_header + statement,
        )
        self.assertEqual(
            formal,
            formal_header + statement,
        )
        self.assertIn(
            b"<urn:example:ontology:base>",
            development_header,
        )
        self.assertIn(
            b"<urn:example:release:2099-01-02:base>",
            formal_header,
        )
        self.assertIn(
            b"<urn:example:release:2099-01-02:document>",
            formal_header,
        )
        self.assertEqual(
            development[-len(statement):],
            formal[-len(statement):],
        )

    def test_publication_errors_propagate_unchanged(self):
        config = project_config()
        products = config.product_graph.products
        invalid = replace(
            config,
            product_graph=ProductGraph(
                products=(
                    products[0],
                    replace(
                        products[1],
                        stable_ontology_iri=None,
                    ),
                ),
            ),
        )

        with self.assertRaises(PublicationError):
            render_ontology_document(
                invalid,
                "document",
                (),
            )

    def test_mapping_compiler_errors_propagate_unchanged(self):
        invalid = replace(
            class_record(),
            expression=None,
        )

        with self.assertRaises(MappingCompileError):
            render_ontology_document(
                project_config(),
                "document",
                (invalid,),
            )

    def test_implementation_dependencies_and_policy_are_neutral(self):
        path = Path("src/coms/ontology_document.py")
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        classes = [
            node.name
            for node in tree.body
            if isinstance(node, ast.ClassDef)
        ]

        self.assertEqual(
            classes,
            ["OntologyDocumentError"],
        )
        for value in (
            "mapping_parser",
            "mapping_record_builder",
            "row_identity",
            "rdflib",
            "openpyxl",
            "Workbook",
            "Worksheet",
            "URIRef",
            "Graph",
            "manifest",
            "archive",
            "reasoner",
        ):
            self.assertNotIn(value, source)

        project_pattern = re.compile(
            r"\b(?:SSN|SOSA|PROV|BFO|CCO|RO|HermiT)\b",
            re.IGNORECASE,
        )
        self.assertIsNone(
            project_pattern.search(source)
        )

    def test_text_to_complete_document_and_row_identity_end_to_end(self):
        resolver = DictResolver(
            {
                ("ex:Material", ENTITY_CLASS): (
                    "urn:example:Material"
                ),
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
            resolver=resolver,
            reasoning="synthetic document integration",
        )
        config = project_config()
        document = render_ontology_document(
            config,
            "document",
            (record,),
        )
        audit = build_row_audit(
            canonical_input_for_mapping_record(
                record,
                RowLocation("Synthetic", 2),
            )
        )

        self.assertEqual(
            document,
            (
                render_ontology_header_bytes(
                    config,
                    "document",
                )
                + render_mapping_record_turtle(
                    record
                )
            ),
        )
        self.assertEqual(
            audit.authoritative_axioms[0].canonical_axiom,
            (
                "SubClassOf(<urn:example:SourceClass> "
                "ObjectIntersectionOf("
                "<urn:example:Material> "
                "ObjectSomeValuesFrom("
                "<urn:example:hasFunction> "
                "<urn:example:SensingFunction>)))"
            ),
        )


if __name__ == "__main__":
    unittest.main()
