import unittest

from coms.config import (
    ExpressionProfile,
    ProductText,
    ProjectConfig,
    PublicationAnnotationRule,
    PublicationProfile,
    ReleaseLayout,
    WorkbookProfile,
    ProductDefinition,
    ProductGraph,
    ProductImport,
)
from dataclasses import FrozenInstanceError, replace

from coms.publication import (
    OntologyAnnotation,
    PublicationError,
    development_import_iris,
    formal_import_iris,
    ontology_annotation_issues,
    publication_annotations,
    release_iri_pattern_issues,
    render_annotation_object_turtle,
    render_ontology_header_bytes,
    release_version_iri,
)
from coms.release_context import (
    FormalReleaseContext,
    FormalReleaseContextError,
)


class OntologyAnnotationTests(
    unittest.TestCase
):
    def test_annotation_is_immutable(self):
        annotation = OntologyAnnotation(
            predicate_iri=(
                "https://example.org/predicate"
            ),
            object_kind="plain_literal",
            value="value",
        )

        with self.assertRaises(
            FrozenInstanceError
        ):
            annotation.value = "changed"

    def test_iri_object_renders_with_full_iri(self):
        annotation = OntologyAnnotation(
            predicate_iri=(
                "https://example.org/predicate"
            ),
            object_kind="iri",
            value="https://example.org/object",
        )

        self.assertEqual(
            ontology_annotation_issues(
                annotation
            ),
            (),
        )

        self.assertEqual(
            render_annotation_object_turtle(
                annotation
            ),
            "<https://example.org/object>",
        )

    def test_plain_literal_rendering_is_deterministic_and_escaped(
        self,
    ):
        annotation = OntologyAnnotation(
            predicate_iri=(
                "https://example.org/predicate"
            ),
            object_kind="plain_literal",
            value='quoted "value"\nnext',
        )

        self.assertEqual(
            render_annotation_object_turtle(
                annotation
            ),
            '"quoted \\"value\\"\\nnext"',
        )

    def test_language_literal_requires_language_and_renders(
        self,
    ):
        invalid = OntologyAnnotation(
            predicate_iri=(
                "https://example.org/predicate"
            ),
            object_kind="language_literal",
            value="label",
        )

        self.assertIn(
            "ANNOTATION_LANGUAGE_REQUIRED",
            {
                issue.code
                for issue
                in ontology_annotation_issues(
                    invalid
                )
            },
        )

        valid = OntologyAnnotation(
            predicate_iri=(
                "https://example.org/predicate"
            ),
            object_kind="language_literal",
            value="label",
            language="en",
        )

        self.assertEqual(
            render_annotation_object_turtle(
                valid
            ),
            '"label"@en',
        )

    def test_typed_literal_requires_datatype_and_renders(
        self,
    ):
        invalid = OntologyAnnotation(
            predicate_iri=(
                "https://example.org/predicate"
            ),
            object_kind="typed_literal",
            value="2099-01-02",
        )

        self.assertIn(
            "ANNOTATION_DATATYPE_REQUIRED",
            {
                issue.code
                for issue
                in ontology_annotation_issues(
                    invalid
                )
            },
        )

        valid = OntologyAnnotation(
            predicate_iri=(
                "https://example.org/predicate"
            ),
            object_kind="typed_literal",
            value="2099-01-02",
            datatype_iri=(
                "https://example.org/date-datatype"
            ),
        )

        self.assertEqual(
            render_annotation_object_turtle(
                valid
            ),
            (
                '"2099-01-02"^^'
                '<https://example.org/date-datatype>'
            ),
        )

    def test_incompatible_language_and_datatype_are_rejected(
        self,
    ):
        iri = OntologyAnnotation(
            predicate_iri=(
                "https://example.org/predicate"
            ),
            object_kind="iri",
            value="https://example.org/object",
            language="en",
            datatype_iri=(
                "https://example.org/datatype"
            ),
        )

        self.assertEqual(
            {
                issue.code
                for issue
                in ontology_annotation_issues(
                    iri
                )
            },
            {
                "ANNOTATION_LANGUAGE_NOT_ALLOWED",
                "ANNOTATION_DATATYPE_NOT_ALLOWED",
            },
        )

        language = OntologyAnnotation(
            predicate_iri=(
                "https://example.org/predicate"
            ),
            object_kind="language_literal",
            value="value",
            language="en",
            datatype_iri=(
                "https://example.org/datatype"
            ),
        )

        self.assertIn(
            "ANNOTATION_DATATYPE_NOT_ALLOWED",
            {
                issue.code
                for issue
                in ontology_annotation_issues(
                    language
                )
            },
        )

        typed = OntologyAnnotation(
            predicate_iri=(
                "https://example.org/predicate"
            ),
            object_kind="typed_literal",
            value="value",
            language="en",
            datatype_iri=(
                "https://example.org/datatype"
            ),
        )

        self.assertIn(
            "ANNOTATION_LANGUAGE_NOT_ALLOWED",
            {
                issue.code
                for issue
                in ontology_annotation_issues(
                    typed
                )
            },
        )

    def test_unknown_object_kind_is_rejected(
        self,
    ):
        annotation = OntologyAnnotation(
            predicate_iri=(
                "https://example.org/predicate"
            ),
            object_kind="unsupported",
            value="value",
        )

        self.assertEqual(
            tuple(
                issue.code
                for issue
                in ontology_annotation_issues(
                    annotation
                )
            ),
            (
                "INVALID_ANNOTATION_OBJECT_KIND",
            ),
        )

    def test_invalid_annotation_raises_structured_publication_error(
        self,
    ):
        annotation = OntologyAnnotation(
            predicate_iri=(
                "https://example.org/predicate"
            ),
            object_kind="typed_literal",
            value="value",
        )

        with self.assertRaises(
            PublicationError
        ) as context:
            render_annotation_object_turtle(
                annotation
            )

        self.assertEqual(
            context.exception.issues[0].code,
            "ANNOTATION_DATATYPE_REQUIRED",
        )


class PublicationVersioningTests(
    unittest.TestCase
):
    def _context(
        self,
    ) -> FormalReleaseContext:
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

    def _product(
        self,
        pattern: str | None = (
            "https://example.org/releases/"
            "{release_identifier}/mapping"
        ),
    ) -> ProductDefinition:
        return ProductDefinition(
            product_key="mapping",
            output_path="build/mapping.ttl",
            product_type="mapping",
            release_iri_pattern=pattern,
        )

    def test_release_version_iri_uses_configured_complete_pattern(
        self,
    ):
        observed = release_version_iri(
            self._product(),
            self._context(),
        )

        self.assertEqual(
            observed,
            (
                "https://example.org/releases/"
                "2099-01-02/mapping"
            ),
        )

    def test_project_specific_literal_path_is_preserved(
        self,
    ):
        product = self._product(
            (
                "https://example.org/releases/"
                "{release_identifier}/"
                "track-alpha/alignment"
            )
        )

        self.assertEqual(
            release_version_iri(
                product,
                self._context(),
            ),
            (
                "https://example.org/releases/"
                "2099-01-02/"
                "track-alpha/alignment"
            ),
        )

    def test_missing_pattern_is_reported(
        self,
    ):
        issues = release_iri_pattern_issues(
            self._product(None)
        )

        self.assertEqual(
            tuple(
                issue.code
                for issue in issues
            ),
            (
                "MISSING_RELEASE_IRI_PATTERN",
            ),
        )

    def test_pattern_requires_exactly_one_release_identifier(
        self,
    ):
        no_placeholder = self._product(
            "https://example.org/releases/mapping"
        )

        duplicate = self._product(
            (
                "https://example.org/"
                "{release_identifier}/"
                "{release_identifier}/mapping"
            )
        )

        self.assertEqual(
            tuple(
                issue.code
                for issue
                in release_iri_pattern_issues(
                    no_placeholder
                )
            ),
            (
                "RELEASE_IDENTIFIER_PLACEHOLDER_COUNT",
            ),
        )

        self.assertEqual(
            tuple(
                issue.code
                for issue
                in release_iri_pattern_issues(
                    duplicate
                )
            ),
            (
                "RELEASE_IDENTIFIER_PLACEHOLDER_COUNT",
            ),
        )

    def test_unknown_replacement_field_is_rejected(
        self,
    ):
        product = self._product(
            (
                "https://example.org/releases/"
                "{release_identifier}/"
                "{product_key}"
            )
        )

        codes = {
            issue.code
            for issue in release_iri_pattern_issues(
                product
            )
        }

        self.assertEqual(
            codes,
            {
                "UNSUPPORTED_RELEASE_IRI_FIELD",
            },
        )

    def test_formatting_and_conversion_are_rejected(
        self,
    ):
        formatted = self._product(
            (
                "https://example.org/"
                "{release_identifier:>12}/mapping"
            )
        )

        converted = self._product(
            (
                "https://example.org/"
                "{release_identifier!r}/mapping"
            )
        )

        self.assertIn(
            "UNSUPPORTED_RELEASE_IRI_FORMATTING",
            {
                issue.code
                for issue in release_iri_pattern_issues(
                    formatted
                )
            },
        )

        self.assertIn(
            "UNSUPPORTED_RELEASE_IRI_CONVERSION",
            {
                issue.code
                for issue in release_iri_pattern_issues(
                    converted
                )
            },
        )

    def test_malformed_pattern_is_reported(
        self,
    ):
        product = self._product(
            (
                "https://example.org/"
                "{release_identifier/mapping"
            )
        )

        self.assertEqual(
            tuple(
                issue.code
                for issue in release_iri_pattern_issues(
                    product
                )
            ),
            (
                "MALFORMED_RELEASE_IRI_PATTERN",
            ),
        )

    def test_formal_release_context_validation_remains_authoritative(
        self,
    ):
        invalid = FormalReleaseContext(
            release_identifier="2099-1-2",
            release_date="2099-01-02",
            git_tag="v2099-01-02",
            source_commit=(
                "0123456789abcdef"
                "0123456789abcdef"
                "01234567"
            ),
        )

        with self.assertRaises(
            FormalReleaseContextError
        ):
            release_version_iri(
                self._product(),
                invalid,
            )

    def test_invalid_pattern_raises_structured_publication_error(
        self,
    ):
        with self.assertRaises(
            PublicationError
        ) as context:
            release_version_iri(
                self._product(None),
                self._context(),
            )

        self.assertEqual(
            context.exception.issues[0].code,
            "MISSING_RELEASE_IRI_PATTERN",
        )




class PublicationAnnotationEvaluationTests(
    unittest.TestCase
):
    def _context(
        self,
    ) -> FormalReleaseContext:
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

    def _config(
        self,
        rules=(),
        *,
        creators=(
            "Creator A",
            "Creator B",
        ),
        contributors=(
            "Contributor A",
        ),
        repository_iri=(
            "https://example.org/repository"
        ),
    ) -> ProjectConfig:
        alignment = ProductDefinition(
            product_key="alignment",
            output_path="build/alignment.ttl",
            product_type="mapping",
            stable_ontology_iri=(
                "https://example.org/alignment"
            ),
            release_iri_pattern=(
                "https://example.org/releases/"
                "{release_identifier}/alignment"
            ),
        )

        integrated = ProductDefinition(
            product_key="integrated",
            output_path="build/integrated.ttl",
            product_type="integrated",
            stable_ontology_iri=(
                "https://example.org/integrated"
            ),
            release_iri_pattern=(
                "https://example.org/releases/"
                "{release_identifier}/integrated"
            ),
        )

        return ProjectConfig(
            project_key="synthetic",
            project_title="Synthetic Mapping",
            repository_root=".",
            authoritative_mapping_source="workbook",
            primary_output="integrated",
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
                    alignment,
                    integrated,
                ),
            ),
            validation_profiles=(),
            publication=PublicationProfile(
                project_title="Synthetic Mapping",
                repository_iri=repository_iri,
                license_iri=(
                    "https://example.org/license"
                ),
                creators=creators,
                contributors=contributors,
                development_status="development",
                product_labels=(
                    ProductText(
                        "alignment",
                        "Alignment Mapping",
                    ),
                    ProductText(
                        "integrated",
                        "Integrated Mapping",
                    ),
                ),
                product_descriptions=(
                    ProductText(
                        "alignment",
                        "Alignment description",
                    ),
                    ProductText(
                        "integrated",
                        "Integrated description",
                    ),
                ),
                annotation_rules=tuple(
                    rules
                ),
            ),
            release_layout=ReleaseLayout(),
        )

    def test_development_evaluation_preserves_rule_order(
        self,
    ):
        config = self._config(
            (
                PublicationAnnotationRule(
                    predicate_iri=(
                        "https://example.org/first"
                    ),
                    object_kind="plain_literal",
                    fixed_value="fixed",
                ),
                PublicationAnnotationRule(
                    predicate_iri=(
                        "https://example.org/repository"
                    ),
                    object_kind="iri",
                    value_source=(
                        "publication.repository_iri"
                    ),
                ),
                PublicationAnnotationRule(
                    predicate_iri=(
                        "https://example.org/type"
                    ),
                    object_kind="plain_literal",
                    value_source="product.type",
                ),
            )
        )

        observed = publication_annotations(
            config,
            "integrated",
        )

        self.assertEqual(
            tuple(
                value.predicate_iri
                for value in observed
            ),
            (
                "https://example.org/first",
                "https://example.org/repository",
                "https://example.org/type",
            ),
        )

        self.assertEqual(
            tuple(
                value.value
                for value in observed
            ),
            (
                "fixed",
                "https://example.org/repository",
                "integrated",
            ),
        )

    def test_multivalued_sources_expand_in_configured_order(
        self,
    ):
        config = self._config(
            (
                PublicationAnnotationRule(
                    predicate_iri=(
                        "https://example.org/creator"
                    ),
                    object_kind="plain_literal",
                    value_source=(
                        "publication.creators"
                    ),
                ),
                PublicationAnnotationRule(
                    predicate_iri=(
                        "https://example.org/contributor"
                    ),
                    object_kind="plain_literal",
                    value_source=(
                        "publication.contributors"
                    ),
                ),
            )
        )

        observed = publication_annotations(
            config,
            "integrated",
        )

        self.assertEqual(
            tuple(
                value.value
                for value in observed
            ),
            (
                "Creator A",
                "Creator B",
                "Contributor A",
            ),
        )

        self.assertEqual(
            tuple(
                value.predicate_iri
                for value in observed
            ),
            (
                "https://example.org/creator",
                "https://example.org/creator",
                "https://example.org/contributor",
            ),
        )

    def test_empty_multivalued_source_emits_nothing_in_place(
        self,
    ):
        config = self._config(
            (
                PublicationAnnotationRule(
                    predicate_iri=(
                        "https://example.org/before"
                    ),
                    object_kind="plain_literal",
                    fixed_value="before",
                ),
                PublicationAnnotationRule(
                    predicate_iri=(
                        "https://example.org/contributor"
                    ),
                    object_kind="plain_literal",
                    value_source=(
                        "publication.contributors"
                    ),
                ),
                PublicationAnnotationRule(
                    predicate_iri=(
                        "https://example.org/after"
                    ),
                    object_kind="plain_literal",
                    fixed_value="after",
                ),
            ),
            contributors=(),
        )

        observed = publication_annotations(
            config,
            "integrated",
        )

        self.assertEqual(
            tuple(
                value.value
                for value in observed
            ),
            (
                "before",
                "after",
            ),
        )

    def test_product_scope_and_applicability_are_filters(
        self,
    ):
        config = self._config(
            (
                PublicationAnnotationRule(
                    predicate_iri=(
                        "https://example.org/alignment-only"
                    ),
                    object_kind="plain_literal",
                    fixed_value="skip-product",
                    product_keys=(
                        "alignment",
                    ),
                ),
                PublicationAnnotationRule(
                    predicate_iri=(
                        "https://example.org/formal-only"
                    ),
                    object_kind="plain_literal",
                    applicability="formal",
                    fixed_value="skip-mode",
                ),
                PublicationAnnotationRule(
                    predicate_iri=(
                        "https://example.org/both"
                    ),
                    object_kind="plain_literal",
                    applicability="both",
                    fixed_value="keep",
                    product_keys=(
                        "integrated",
                    ),
                ),
            )
        )

        observed = publication_annotations(
            config,
            "integrated",
        )

        self.assertEqual(
            tuple(
                value.value
                for value in observed
            ),
            (
                "keep",
            ),
        )

    def test_product_text_sources_resolve_exact_keyed_values(
        self,
    ):
        config = self._config(
            (
                PublicationAnnotationRule(
                    predicate_iri=(
                        "https://example.org/label"
                    ),
                    object_kind="plain_literal",
                    value_source="product.label",
                ),
                PublicationAnnotationRule(
                    predicate_iri=(
                        "https://example.org/description"
                    ),
                    object_kind="plain_literal",
                    value_source=(
                        "product.description"
                    ),
                ),
            )
        )

        observed = publication_annotations(
            config,
            "integrated",
        )

        self.assertEqual(
            tuple(
                value.value
                for value in observed
            ),
            (
                "Integrated Mapping",
                "Integrated description",
            ),
        )

    def test_formal_evaluation_resolves_release_sources(
        self,
    ):
        config = self._config(
            (
                PublicationAnnotationRule(
                    predicate_iri=(
                        "https://example.org/version"
                    ),
                    object_kind="iri",
                    applicability="formal",
                    value_source=(
                        "product.release_version_iri"
                    ),
                ),
                PublicationAnnotationRule(
                    predicate_iri=(
                        "https://example.org/release-id"
                    ),
                    object_kind="plain_literal",
                    applicability="formal",
                    value_source=(
                        "release.release_identifier"
                    ),
                ),
                PublicationAnnotationRule(
                    predicate_iri=(
                        "https://example.org/date"
                    ),
                    object_kind="typed_literal",
                    applicability="formal",
                    value_source="release.release_date",
                    datatype_iri=(
                        "https://example.org/date-type"
                    ),
                ),
                PublicationAnnotationRule(
                    predicate_iri=(
                        "https://example.org/tag"
                    ),
                    object_kind="plain_literal",
                    applicability="formal",
                    value_source="release.git_tag",
                ),
                PublicationAnnotationRule(
                    predicate_iri=(
                        "https://example.org/commit"
                    ),
                    object_kind="plain_literal",
                    applicability="formal",
                    value_source=(
                        "release.source_commit"
                    ),
                ),
            )
        )

        observed = publication_annotations(
            config,
            "integrated",
            self._context(),
        )

        self.assertEqual(
            tuple(
                value.value
                for value in observed
            ),
            (
                (
                    "https://example.org/releases/"
                    "2099-01-02/integrated"
                ),
                "2099-01-02",
                "2099-01-02",
                "v2099-01-02",
                (
                    "0123456789abcdef"
                    "0123456789abcdef"
                    "01234567"
                ),
            ),
        )

    def test_formal_context_validation_remains_authoritative(
        self,
    ):
        config = self._config(
            (
                PublicationAnnotationRule(
                    predicate_iri=(
                        "https://example.org/formal"
                    ),
                    object_kind="plain_literal",
                    applicability="formal",
                    fixed_value="value",
                ),
            )
        )

        invalid = FormalReleaseContext(
            release_identifier="2099-1-2",
            release_date="2099-01-02",
            git_tag="v2099-01-02",
            source_commit=(
                "0123456789abcdef"
                "0123456789abcdef"
                "01234567"
            ),
        )

        with self.assertRaises(
            FormalReleaseContextError
        ):
            publication_annotations(
                config,
                "integrated",
                invalid,
            )

    def test_unknown_and_duplicate_product_identity_are_errors(
        self,
    ):
        config = self._config()

        with self.assertRaises(
            PublicationError
        ) as unknown:
            publication_annotations(
                config,
                "missing",
            )

        self.assertEqual(
            unknown.exception.issues[0].code,
            "UNKNOWN_PUBLICATION_PRODUCT",
        )

        duplicate = replace(
            config,
            product_graph=ProductGraph(
                products=(
                    config.product_graph.products[0],
                    config.product_graph.products[1],
                    replace(
                        config.product_graph.products[1],
                        output_path=(
                            "build/duplicate.ttl"
                        ),
                    ),
                ),
            ),
        )

        with self.assertRaises(
            PublicationError
        ) as ambiguous:
            publication_annotations(
                duplicate,
                "integrated",
            )

        self.assertEqual(
            ambiguous.exception.issues[0].code,
            "AMBIGUOUS_PUBLICATION_PRODUCT",
        )

    def test_missing_scalar_source_is_runtime_structured_error(
        self,
    ):
        config = self._config(
            (
                PublicationAnnotationRule(
                    predicate_iri=(
                        "https://example.org/repository"
                    ),
                    object_kind="iri",
                    value_source=(
                        "publication.repository_iri"
                    ),
                ),
            ),
            repository_iri=None,
        )

        with self.assertRaises(
            PublicationError
        ) as context:
            publication_annotations(
                config,
                "integrated",
            )

        self.assertEqual(
            context.exception.issues[0].code,
            "ANNOTATION_VALUE_SOURCE_UNAVAILABLE",
        )

    def test_invalid_value_origin_and_source_are_runtime_errors(
        self,
    ):
        both = self._config(
            (
                PublicationAnnotationRule(
                    predicate_iri=(
                        "https://example.org/predicate"
                    ),
                    object_kind="plain_literal",
                    value_source=(
                        "publication.project_title"
                    ),
                    fixed_value="fixed",
                ),
            )
        )

        with self.assertRaises(
            PublicationError
        ) as origin:
            publication_annotations(
                both,
                "integrated",
            )

        self.assertEqual(
            origin.exception.issues[0].code,
            "ANNOTATION_VALUE_ORIGIN_COUNT",
        )

        unsupported = self._config(
            (
                PublicationAnnotationRule(
                    predicate_iri=(
                        "https://example.org/predicate"
                    ),
                    object_kind="plain_literal",
                    value_source="unsupported.source",
                ),
            )
        )

        with self.assertRaises(
            PublicationError
        ) as source:
            publication_annotations(
                unsupported,
                "integrated",
            )

        self.assertEqual(
            source.exception.issues[0].code,
            "UNSUPPORTED_ANNOTATION_VALUE_SOURCE",
        )

    def test_evaluation_enforces_annotation_object_shape(
        self,
    ):
        config = self._config(
            (
                PublicationAnnotationRule(
                    predicate_iri=(
                        "https://example.org/label"
                    ),
                    object_kind="language_literal",
                    fixed_value="label",
                ),
            )
        )

        with self.assertRaises(
            PublicationError
        ) as context:
            publication_annotations(
                config,
                "integrated",
            )

        self.assertEqual(
            context.exception.issues[0].code,
            "ANNOTATION_LANGUAGE_REQUIRED",
        )


class OntologyHeaderAssemblyTests(
    unittest.TestCase
):
    OWL_ONTOLOGY = (
        "http://www.w3.org/2002/07/owl#Ontology"
    )

    OWL_IMPORTS = (
        "http://www.w3.org/2002/07/owl#imports"
    )

    def _context(
        self,
    ) -> FormalReleaseContext:
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

    def _config(
        self,
        rules=(),
    ) -> ProjectConfig:
        alignment = ProductDefinition(
            product_key="alignment",
            output_path="build/alignment.ttl",
            product_type="mapping",
            stable_ontology_iri=(
                "https://example.org/alignment"
            ),
            release_iri_pattern=(
                "https://example.org/releases/"
                "{release_identifier}/alignment"
            ),
        )

        integrated = ProductDefinition(
            product_key="integrated",
            output_path="build/integrated.ttl",
            product_type="integrated",
            stable_ontology_iri=(
                "https://example.org/integrated"
            ),
            release_iri_pattern=(
                "https://example.org/releases/"
                "{release_identifier}/integrated"
            ),
        )

        return ProjectConfig(
            project_key="synthetic",
            project_title="Synthetic Mapping",
            repository_root=".",
            authoritative_mapping_source="workbook",
            primary_output="integrated",
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
                    alignment,
                    integrated,
                ),
            ),
            validation_profiles=(),
            publication=PublicationProfile(
                project_title="Synthetic Mapping",
                product_labels=(
                    ProductText(
                        "alignment",
                        "Alignment Mapping",
                    ),
                    ProductText(
                        "integrated",
                        "Integrated Mapping",
                    ),
                ),
                annotation_rules=tuple(
                    rules
                ),
            ),
            release_layout=ReleaseLayout(),
        )

    def test_header_uses_stable_subject_annotations_then_imports(
        self,
    ):
        config = self._config(
            (
                PublicationAnnotationRule(
                    predicate_iri=(
                        "https://example.org/label"
                    ),
                    object_kind="plain_literal",
                    value_source="product.label",
                ),
                PublicationAnnotationRule(
                    predicate_iri=(
                        "https://example.org/type"
                    ),
                    object_kind="plain_literal",
                    value_source="product.type",
                ),
            )
        )

        integrated = replace(
            config.product_graph.products[1],
            imports=(
                "https://example.org/external-a",
                "https://example.org/external-b",
            ),
        )

        config = replace(
            config,
            product_graph=ProductGraph(
                products=(
                    config.product_graph.products[0],
                    integrated,
                ),
            ),
        )

        observed = render_ontology_header_bytes(
            config,
            "integrated",
        )

        expected = (
            "<https://example.org/integrated> "
            f"a <{self.OWL_ONTOLOGY}> ;\n"
            "    <https://example.org/label> "
            "\"Integrated Mapping\" ;\n"
            "    <https://example.org/type> "
            "\"integrated\" ;\n"
            f"    <{self.OWL_IMPORTS}> "
            "<https://example.org/external-a>,\n"
            "        <https://example.org/external-b> .\n"
        ).encode(
            "utf-8"
        )

        self.assertEqual(
            observed,
            expected,
        )

    def test_formal_header_keeps_stable_subject_and_version_is_metadata(
        self,
    ):
        config = self._config(
            (
                PublicationAnnotationRule(
                    predicate_iri=(
                        "https://example.org/version"
                    ),
                    object_kind="iri",
                    applicability="formal",
                    value_source=(
                        "product.release_version_iri"
                    ),
                ),
            )
        )

        text = render_ontology_header_bytes(
            config,
            "integrated",
            self._context(),
        ).decode(
            "utf-8"
        )

        self.assertTrue(
            text.startswith(
                "<https://example.org/integrated> "
            )
        )

        self.assertIn(
            (
                "<https://example.org/version> "
                "<https://example.org/releases/"
                "2099-01-02/integrated>"
            ),
            text,
        )

        self.assertFalse(
            text.startswith(
                (
                    "<https://example.org/releases/"
                    "2099-01-02/integrated>"
                )
            )
        )

    def test_empty_header_is_one_complete_ontology_statement(
        self,
    ):
        config = self._config()

        observed = render_ontology_header_bytes(
            config,
            "alignment",
        )

        self.assertEqual(
            observed,
            (
                "<https://example.org/alignment> "
                f"a <{self.OWL_ONTOLOGY}> .\n"
            ).encode(
                "utf-8"
            ),
        )

    def test_annotations_without_imports_end_with_period(
        self,
    ):
        config = self._config(
            (
                PublicationAnnotationRule(
                    predicate_iri=(
                        "https://example.org/label"
                    ),
                    object_kind="plain_literal",
                    value_source="product.label",
                ),
            )
        )

        observed = render_ontology_header_bytes(
            config,
            "alignment",
        ).decode(
            "utf-8"
        )

        self.assertEqual(
            observed.splitlines()[-1],
            (
                "    <https://example.org/label> "
                "\"Alignment Mapping\" ."
            ),
        )

    def test_imports_without_annotations_are_structural_tail(
        self,
    ):
        config = self._config()

        alignment = replace(
            config.product_graph.products[0],
            imports=(
                "https://example.org/external",
            ),
        )

        config = replace(
            config,
            product_graph=ProductGraph(
                products=(
                    alignment,
                    config.product_graph.products[1],
                ),
            ),
        )

        observed = render_ontology_header_bytes(
            config,
            "alignment",
        ).decode(
            "utf-8"
        )

        self.assertEqual(
            observed.splitlines(),
            [
                (
                    "<https://example.org/alignment> "
                    f"a <{self.OWL_ONTOLOGY}> ;"
                ),
                (
                    f"    <{self.OWL_IMPORTS}> "
                    "<https://example.org/external> ."
                ),
            ],
        )

    def test_resolved_import_order_is_preserved(
        self,
    ):
        config = self._config()

        integrated = replace(
            config.product_graph.products[1],
            imports=(
                "https://example.org/z",
                "https://example.org/a",
            ),
        )

        config = replace(
            config,
            product_graph=ProductGraph(
                products=(
                    config.product_graph.products[0],
                    integrated,
                ),
            ),
        )

        text = render_ontology_header_bytes(
            config,
            "integrated",
        ).decode(
            "utf-8"
        )

        self.assertLess(
            text.index(
                "<https://example.org/z>"
            ),
            text.index(
                "<https://example.org/a>"
            ),
        )

    def test_formal_product_import_uses_release_identity(
        self,
    ):
        config = self._config()

        integrated = replace(
            config.product_graph.products[1],
            product_imports=(
                ProductImport(
                    product_key="alignment",
                    formal_target="release",
                ),
            ),
        )

        config = replace(
            config,
            product_graph=ProductGraph(
                products=(
                    config.product_graph.products[0],
                    integrated,
                ),
            ),
        )

        text = render_ontology_header_bytes(
            config,
            "integrated",
            self._context(),
        ).decode(
            "utf-8"
        )

        self.assertIn(
            (
                "<https://example.org/releases/"
                "2099-01-02/alignment>"
            ),
            text,
        )

        self.assertNotIn(
            (
                f"<{self.OWL_IMPORTS}> "
                "<https://example.org/alignment>"
            ),
            text,
        )

    def test_duplicate_resolved_imports_are_rejected(
        self,
    ):
        config = self._config()

        alignment = replace(
            config.product_graph.products[0],
            imports=(
                "https://example.org/external",
                "https://example.org/external",
            ),
        )

        config = replace(
            config,
            product_graph=ProductGraph(
                products=(
                    alignment,
                    config.product_graph.products[1],
                ),
            ),
        )

        with self.assertRaises(
            PublicationError
        ) as context:
            render_ontology_header_bytes(
                config,
                "alignment",
            )

        self.assertEqual(
            context.exception.issues[0].code,
            "DUPLICATE_ONTOLOGY_IMPORT",
        )

    def test_annotation_rule_cannot_emit_owl_imports(
        self,
    ):
        config = self._config(
            (
                PublicationAnnotationRule(
                    predicate_iri=self.OWL_IMPORTS,
                    object_kind="iri",
                    fixed_value=(
                        "https://example.org/not-governed"
                    ),
                ),
            )
        )

        with self.assertRaises(
            PublicationError
        ) as context:
            render_ontology_header_bytes(
                config,
                "integrated",
            )

        self.assertEqual(
            context.exception.issues[0].code,
            "RESERVED_ONTOLOGY_HEADER_PREDICATE",
        )

    def test_header_requires_stable_ontology_identity(
        self,
    ):
        config = self._config()

        alignment = replace(
            config.product_graph.products[0],
            stable_ontology_iri=None,
        )

        config = replace(
            config,
            product_graph=ProductGraph(
                products=(
                    alignment,
                    config.product_graph.products[1],
                ),
            ),
        )

        with self.assertRaises(
            PublicationError
        ) as context:
            render_ontology_header_bytes(
                config,
                "alignment",
            )

        self.assertEqual(
            context.exception.issues[0].code,
            "ANNOTATION_VALUE_SOURCE_UNAVAILABLE",
        )

    def test_header_is_deterministic_full_iri_and_exactly_one_final_lf(
        self,
    ):
        config = self._config(
            (
                PublicationAnnotationRule(
                    predicate_iri=(
                        "https://example.org/label"
                    ),
                    object_kind="plain_literal",
                    value_source="product.label",
                ),
            )
        )

        first = render_ontology_header_bytes(
            config,
            "integrated",
        )

        second = render_ontology_header_bytes(
            config,
            "integrated",
        )

        self.assertEqual(
            first,
            second,
        )

        self.assertTrue(
            first.endswith(
                b".\n"
            )
        )

        self.assertFalse(
            first.endswith(
                b"\n\n"
            )
        )

        self.assertNotIn(
            b"@prefix",
            first,
        )

        self.assertNotIn(
            b"owl:",
            first,
        )


class PublicationImportResolutionTests(
    unittest.TestCase
):
    def _context(
        self,
    ) -> FormalReleaseContext:
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

    def _upstream(
        self,
        *,
        key: str = "upstream",
        stable: str | None = (
            "https://example.org/upstream"
        ),
        pattern: str | None = (
            "https://example.org/releases/"
            "{release_identifier}/upstream"
        ),
    ) -> ProductDefinition:
        return ProductDefinition(
            product_key=key,
            output_path=(
                f"build/{key}.ttl"
            ),
            product_type="mapping",
            stable_ontology_iri=stable,
            release_iri_pattern=pattern,
        )

    def test_development_imports_are_literal_then_stable_products(
        self,
    ):
        alpha = self._upstream(
            key="alpha",
            stable="https://example.org/alpha",
        )

        beta = self._upstream(
            key="beta",
            stable="https://example.org/beta",
        )

        consumer = ProductDefinition(
            product_key="consumer",
            output_path="build/consumer.ttl",
            product_type="mapping",
            imports=(
                "https://example.org/external-a",
                "https://example.org/external-b",
            ),
            product_imports=(
                ProductImport(
                    product_key="beta",
                    formal_target="release",
                ),
                ProductImport(
                    product_key="alpha",
                    formal_target="stable",
                ),
            ),
        )

        observed = development_import_iris(
            consumer,
            ProductGraph(
                products=(
                    consumer,
                    alpha,
                    beta,
                ),
            ),
        )

        self.assertEqual(
            observed,
            (
                "https://example.org/external-a",
                "https://example.org/external-b",
                "https://example.org/beta",
                "https://example.org/alpha",
            ),
        )

    def test_formal_imports_resolve_stable_and_release_targets(
        self,
    ):
        stable_target = self._upstream(
            key="stable-target",
            stable=(
                "https://example.org/stable-target"
            ),
        )

        release_target = self._upstream(
            key="release-target",
            stable=(
                "https://example.org/release-target"
            ),
            pattern=(
                "https://example.org/releases/"
                "{release_identifier}/release-target"
            ),
        )

        consumer = ProductDefinition(
            product_key="consumer",
            output_path="build/consumer.ttl",
            product_type="mapping",
            imports=(
                "https://example.org/external",
            ),
            product_imports=(
                ProductImport(
                    product_key="stable-target",
                    formal_target="stable",
                ),
                ProductImport(
                    product_key="release-target",
                    formal_target="release",
                ),
            ),
        )

        observed = formal_import_iris(
            consumer,
            ProductGraph(
                products=(
                    consumer,
                    stable_target,
                    release_target,
                ),
            ),
            self._context(),
        )

        self.assertEqual(
            observed,
            (
                "https://example.org/external",
                "https://example.org/stable-target",
                (
                    "https://example.org/releases/"
                    "2099-01-02/release-target"
                ),
            ),
        )

    def test_product_dependencies_have_no_import_semantics(
        self,
    ):
        build_helper = self._upstream(
            key="build-helper",
        )

        consumer = ProductDefinition(
            product_key="consumer",
            output_path="build/consumer.ttl",
            product_type="mapping",
            product_dependencies=(
                "build-helper",
            ),
        )

        graph = ProductGraph(
            products=(
                consumer,
                build_helper,
            ),
        )

        self.assertEqual(
            development_import_iris(
                consumer,
                graph,
            ),
            (),
        )

        self.assertEqual(
            formal_import_iris(
                consumer,
                graph,
                self._context(),
            ),
            (),
        )

    def test_unknown_product_import_target_is_structured_error(
        self,
    ):
        consumer = ProductDefinition(
            product_key="consumer",
            output_path="build/consumer.ttl",
            product_type="mapping",
            product_imports=(
                ProductImport(
                    product_key="missing",
                    formal_target="stable",
                ),
            ),
        )

        with self.assertRaises(
            PublicationError
        ) as context:
            development_import_iris(
                consumer,
                ProductGraph(
                    products=(
                        consumer,
                    ),
                ),
            )

        self.assertEqual(
            context.exception.issues[0].code,
            "UNKNOWN_PRODUCT_IMPORT_TARGET",
        )

    def test_duplicate_product_keys_make_import_target_ambiguous(
        self,
    ):
        first = self._upstream(
            key="upstream",
        )

        second = self._upstream(
            key="upstream",
            stable=(
                "https://example.org/other-upstream"
            ),
        )

        consumer = ProductDefinition(
            product_key="consumer",
            output_path="build/consumer.ttl",
            product_type="mapping",
            product_imports=(
                ProductImport(
                    product_key="upstream",
                    formal_target="stable",
                ),
            ),
        )

        with self.assertRaises(
            PublicationError
        ) as context:
            development_import_iris(
                consumer,
                ProductGraph(
                    products=(
                        consumer,
                        first,
                        second,
                    ),
                ),
            )

        self.assertEqual(
            context.exception.issues[0].code,
            "AMBIGUOUS_PRODUCT_IMPORT_TARGET",
        )

    def test_missing_stable_identity_is_structured_error(
        self,
    ):
        upstream = self._upstream(
            stable=None,
        )

        consumer = ProductDefinition(
            product_key="consumer",
            output_path="build/consumer.ttl",
            product_type="mapping",
            product_imports=(
                ProductImport(
                    product_key="upstream",
                    formal_target="stable",
                ),
            ),
        )

        with self.assertRaises(
            PublicationError
        ) as context:
            development_import_iris(
                consumer,
                ProductGraph(
                    products=(
                        consumer,
                        upstream,
                    ),
                ),
            )

        self.assertEqual(
            context.exception.issues[0].code,
            "MISSING_STABLE_IMPORT_IDENTITY",
        )

    def test_release_target_uses_version_pattern_validation(
        self,
    ):
        upstream = self._upstream(
            pattern=None,
        )

        consumer = ProductDefinition(
            product_key="consumer",
            output_path="build/consumer.ttl",
            product_type="mapping",
            product_imports=(
                ProductImport(
                    product_key="upstream",
                    formal_target="release",
                ),
            ),
        )

        with self.assertRaises(
            PublicationError
        ) as context:
            formal_import_iris(
                consumer,
                ProductGraph(
                    products=(
                        consumer,
                        upstream,
                    ),
                ),
                self._context(),
            )

        self.assertEqual(
            context.exception.issues[0].code,
            "MISSING_RELEASE_IRI_PATTERN",
        )

    def test_invalid_formal_target_is_structured_error(
        self,
    ):
        upstream = self._upstream()

        consumer = ProductDefinition(
            product_key="consumer",
            output_path="build/consumer.ttl",
            product_type="mapping",
            product_imports=(
                ProductImport(
                    product_key="upstream",
                    formal_target="unsupported",
                ),
            ),
        )

        with self.assertRaises(
            PublicationError
        ) as context:
            formal_import_iris(
                consumer,
                ProductGraph(
                    products=(
                        consumer,
                        upstream,
                    ),
                ),
                self._context(),
            )

        self.assertEqual(
            context.exception.issues[0].code,
            "UNSUPPORTED_PRODUCT_IMPORT_FORMAL_TARGET",
        )

    def test_formal_imports_require_valid_release_context(
        self,
    ):
        consumer = ProductDefinition(
            product_key="consumer",
            output_path="build/consumer.ttl",
            product_type="mapping",
        )

        invalid = FormalReleaseContext(
            release_identifier="2099-1-2",
            release_date="2099-01-02",
            git_tag="v2099-01-02",
            source_commit=(
                "0123456789abcdef"
                "0123456789abcdef"
                "01234567"
            ),
        )

        with self.assertRaises(
            FormalReleaseContextError
        ):
            formal_import_iris(
                consumer,
                ProductGraph(
                    products=(
                        consumer,
                    ),
                ),
                invalid,
            )


if __name__ == "__main__":
    unittest.main()
