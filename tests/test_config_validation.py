from dataclasses import replace
import unittest

from coms.config import (
    ExpressionProfile,
    FixedCountPolicy,
    HeaderBinding,
    PrefixBinding,
    ProductDefinition,
    ProductGraph,
    ProductImport,
    ProductText,
    ProjectConfig,
    PublicationAnnotationRule,
    PublicationProfile,
    ReleaseLayout,
    ValidationProfile,
    VocabularyProfile,
    WorkbookProfile,
    validate_project_config,
)


class ConfigurationValidationTests(unittest.TestCase):
    def _config(self) -> ProjectConfig:
        workbook = WorkbookProfile(
            workbook_path="fixtures/mapping.xlsx",
            sheet_selectors=("Mappings",),
            header_bindings=(
                HeaderBinding(
                    "row_id",
                    "RowID",
                ),
                HeaderBinding(
                    "source",
                    "Source",
                ),
                HeaderBinding(
                    "target",
                    "Target",
                ),
            ),
            required_columns=(
                "RowID",
                "Source",
                "Target",
            ),
            row_id_column="RowID",
            allowed_expression_types=(
                "class_mapping",
            ),
        )

        source = VocabularyProfile(
            vocabulary_key="source",
            role="source",
            namespace_iris=(
                "https://example.org/source/",
            ),
            prefixes=(
                PrefixBinding(
                    "src",
                    "https://example.org/source/",
                ),
            ),
            permitted_products=(
                "alignment",
                "integrated",
            ),
        )

        target = VocabularyProfile(
            vocabulary_key="target",
            role="target",
            namespace_iris=(
                "https://example.org/target/",
            ),
            prefixes=(
                PrefixBinding(
                    "tgt",
                    "https://example.org/target/",
                ),
            ),
            permitted_products=(
                "integrated",
            ),
        )

        validation = ValidationProfile(
            profile_key="default",
            rdf_parser_checks=True,
            exact_product_list=(
                "alignment",
                "integrated",
            ),
            fixed_count_policies=(
                FixedCountPolicy(
                    "mapping-count",
                    5,
                ),
            ),
        )

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
            permitted_vocabularies=(
                "source",
            ),
            validation_profile="default",
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
            product_dependencies=(
                "alignment",
            ),
            permitted_vocabularies=(
                "source",
                "target",
            ),
            validation_profile="default",
        )

        return ProjectConfig(
            project_key="synthetic",
            project_title="Synthetic Mapping",
            repository_root=".",
            authoritative_mapping_source="workbook",
            primary_output="integrated",
            generated_warning="GENERATED FILE",
            configuration_schema_version="1",
            workbook=workbook,
            vocabularies=(
                source,
                target,
            ),
            expressions=ExpressionProfile(
                canonicalization_version="synthetic-v1",
            ),
            product_graph=ProductGraph(
                products=(
                    alignment,
                    integrated,
                ),
            ),
            validation_profiles=(
                validation,
            ),
            publication=PublicationProfile(
                project_title="Synthetic Mapping",
                product_labels=(
                    ProductText(
                        "integrated",
                        "Integrated Mapping",
                    ),
                ),
            ),
            release_layout=ReleaseLayout(
                archive_prefix="synthetic",
            ),
        )

    @staticmethod
    def _codes(config: ProjectConfig) -> set[str]:
        return {
            issue.code
            for issue in validate_project_config(config)
        }

    def test_valid_configuration_has_no_issues(self):
        self.assertEqual(
            validate_project_config(self._config()),
            (),
        )

    def test_validation_does_not_require_filesystem_paths_to_exist(self):
        config = self._config()

        workbook = replace(
            config.workbook,
            workbook_path=(
                "/definitely/not/a/real/"
                "mapping-workbook.xlsx"
            ),
        )

        products = tuple(
            replace(
                product,
                output_path=(
                    "/definitely/not/a/real/"
                    f"{product.product_key}.ttl"
                ),
            )
            for product in config.product_graph.products
        )

        config = replace(
            config,
            repository_root=(
                "/definitely/not/a/real/repository"
            ),
            workbook=workbook,
            product_graph=ProductGraph(
                products=products,
            ),
        )

        self.assertEqual(
            validate_project_config(config),
            (),
        )

    def test_duplicate_top_level_keys_are_reported(self):
        config = self._config()

        config = replace(
            config,
            vocabularies=(
                *config.vocabularies,
                config.vocabularies[0],
            ),
            product_graph=ProductGraph(
                products=(
                    *config.product_graph.products,
                    config.product_graph.products[0],
                ),
            ),
            validation_profiles=(
                *config.validation_profiles,
                config.validation_profiles[0],
            ),
        )

        self.assertTrue(
            {
                "duplicate_vocabulary_key",
                "duplicate_product_key",
                "duplicate_validation_profile_key",
            }.issubset(self._codes(config))
        )

    def test_invalid_vocabulary_role_is_reported(self):
        config = self._config()

        invalid = replace(
            config.vocabularies[0],
            role="unsupported",
        )

        config = replace(
            config,
            vocabularies=(
                invalid,
                config.vocabularies[1],
            ),
        )

        self.assertIn(
            "invalid_vocabulary_role",
            self._codes(config),
        )

    def test_unknown_product_references_are_reported(self):
        config = self._config()

        integrated = replace(
            config.product_graph.products[1],
            product_dependencies=(
                "missing-product",
            ),
            permitted_vocabularies=(
                "missing-vocabulary",
            ),
            validation_profile="missing-profile",
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

        self.assertTrue(
            {
                "unknown_product_dependency",
                "unknown_vocabulary_reference",
                "unknown_validation_profile",
            }.issubset(self._codes(config))
        )

    def test_unknown_references_from_other_profiles_are_reported(self):
        config = self._config()

        source = replace(
            config.vocabularies[0],
            permitted_products=(
                "missing-product",
            ),
        )

        validation = replace(
            config.validation_profiles[0],
            exact_product_list=(
                "missing-product",
            ),
        )

        publication = replace(
            config.publication,
            product_labels=(
                ProductText(
                    "missing-product",
                    "Missing",
                ),
            ),
        )

        config = replace(
            config,
            vocabularies=(
                source,
                config.vocabularies[1],
            ),
            validation_profiles=(
                validation,
            ),
            publication=publication,
        )

        self.assertTrue(
            {
                "unknown_product_reference",
                "unknown_validation_product",
                "unknown_publication_product",
            }.issubset(self._codes(config))
        )

    def test_contradictory_constraints_are_reported(self):
        config = self._config()

        source = replace(
            config.vocabularies[0],
            permitted_products=(
                "integrated",
            ),
            prohibited_products=(
                "integrated",
            ),
        )

        integrated = replace(
            config.product_graph.products[1],
            permitted_vocabularies=(
                "target",
            ),
            prohibited_vocabularies=(
                "target",
            ),
        )

        config = replace(
            config,
            vocabularies=(
                source,
                config.vocabularies[1],
            ),
            product_graph=ProductGraph(
                products=(
                    config.product_graph.products[0],
                    integrated,
                ),
            ),
        )

        self.assertTrue(
            {
                "contradictory_product_constraint",
                "contradictory_vocabulary_constraint",
            }.issubset(self._codes(config))
        )

    def test_explicit_cross_direction_constraints_cannot_conflict(self):
        config = self._config()

        source = replace(
            config.vocabularies[0],
            permitted_products=(
                "integrated",
            ),
            prohibited_products=(),
        )

        target = replace(
            config.vocabularies[1],
            permitted_products=(),
            prohibited_products=(
                "integrated",
            ),
        )

        integrated = replace(
            config.product_graph.products[1],
            permitted_vocabularies=(
                "target",
            ),
            prohibited_vocabularies=(
                "source",
            ),
        )

        config = replace(
            config,
            vocabularies=(
                source,
                target,
            ),
            product_graph=ProductGraph(
                products=(
                    config.product_graph.products[0],
                    integrated,
                ),
            ),
        )

        conflicts = tuple(
            issue
            for issue in validate_project_config(config)
            if issue.code == "cross_constraint_conflict"
        )

        self.assertEqual(
            len(conflicts),
            2,
        )

        self.assertEqual(
            tuple(
                issue.path
                for issue in conflicts
            ),
            (
                "vocabulary_product_constraints[source,integrated]",
                "vocabulary_product_constraints[target,integrated]",
            ),
        )

        self.assertIn(
            "explicitly permits product",
            conflicts[0].message,
        )

        self.assertIn(
            "explicitly prohibits product",
            conflicts[1].message,
        )

    def test_product_import_reference_and_formal_target_are_validated(self):
        config = self._config()

        integrated = replace(
            config.product_graph.products[1],
            product_imports=(
                ProductImport(
                    product_key="missing-product",
                    formal_target="unsupported",
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

        self.assertTrue(
            {
                "unknown_product_import",
                "invalid_product_import_formal_target",
            }.issubset(
                self._codes(config)
            )
        )

    def test_product_import_does_not_imply_product_dependency(self):
        config = self._config()

        integrated = replace(
            config.product_graph.products[1],
            product_dependencies=(),
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

        self.assertEqual(
            validate_project_config(config),
            (),
        )

    def test_product_import_target_requires_stable_ontology_iri(self):
        config = self._config()

        alignment = replace(
            config.product_graph.products[0],
            stable_ontology_iri=None,
        )

        integrated = replace(
            config.product_graph.products[1],
            product_imports=(
                ProductImport(
                    product_key="alignment",
                    formal_target="stable",
                ),
            ),
        )

        config = replace(
            config,
            product_graph=ProductGraph(
                products=(
                    alignment,
                    integrated,
                ),
            ),
        )

        self.assertIn(
            (
                "product_import_target_missing_"
                "stable_ontology_iri"
            ),
            self._codes(config),
        )

    def test_release_product_import_requires_release_pattern_only_for_release_target(
        self,
    ):
        config = self._config()

        alignment = replace(
            config.product_graph.products[0],
            release_iri_pattern=None,
        )

        release_import = replace(
            config.product_graph.products[1],
            product_imports=(
                ProductImport(
                    product_key="alignment",
                    formal_target="release",
                ),
            ),
        )

        release_config = replace(
            config,
            product_graph=ProductGraph(
                products=(
                    alignment,
                    release_import,
                ),
            ),
        )

        self.assertIn(
            (
                "product_import_target_missing_"
                "release_iri_pattern"
            ),
            self._codes(
                release_config
            ),
        )

        stable_import = replace(
            release_import,
            product_imports=(
                ProductImport(
                    product_key="alignment",
                    formal_target="stable",
                ),
            ),
        )

        stable_config = replace(
            config,
            product_graph=ProductGraph(
                products=(
                    alignment,
                    stable_import,
                ),
            ),
        )

        self.assertEqual(
            validate_project_config(
                stable_config
            ),
            (),
        )

    def test_annotation_rule_enumerations_are_validated(self):
        config = self._config()

        publication = replace(
            config.publication,
            annotation_rules=(
                PublicationAnnotationRule(
                    predicate_iri=(
                        "https://example.org/predicate"
                    ),
                    object_kind="unsupported",
                    applicability="sometimes",
                    value_source="unsupported.source",
                ),
            ),
        )

        config = replace(
            config,
            publication=publication,
        )

        self.assertTrue(
            {
                "invalid_annotation_object_kind",
                "invalid_annotation_applicability",
                "invalid_annotation_value_source",
            }.issubset(
                self._codes(config)
            )
        )

    def test_annotation_rule_requires_exactly_one_value_origin(self):
        config = self._config()

        publication = replace(
            config.publication,
            annotation_rules=(
                PublicationAnnotationRule(
                    predicate_iri=(
                        "https://example.org/one"
                    ),
                    object_kind="plain_literal",
                ),
                PublicationAnnotationRule(
                    predicate_iri=(
                        "https://example.org/two"
                    ),
                    object_kind="plain_literal",
                    value_source=(
                        "publication.project_title"
                    ),
                    fixed_value="fixed",
                ),
            ),
        )

        config = replace(
            config,
            publication=publication,
        )

        issues = tuple(
            issue
            for issue in validate_project_config(
                config
            )
            if issue.code
            == "annotation_value_origin_count"
        )

        self.assertEqual(
            len(issues),
            2,
        )

    def test_annotation_rule_product_scope_is_validated(self):
        config = self._config()

        publication = replace(
            config.publication,
            annotation_rules=(
                PublicationAnnotationRule(
                    predicate_iri=(
                        "https://example.org/predicate"
                    ),
                    object_kind="plain_literal",
                    fixed_value="value",
                    product_keys=(
                        "missing",
                        "missing",
                    ),
                ),
            ),
        )

        config = replace(
            config,
            publication=publication,
        )

        self.assertTrue(
            {
                "duplicate_annotation_rule_product",
                "unknown_annotation_rule_product",
            }.issubset(
                self._codes(config)
            )
        )

    def test_annotation_rule_object_shape_is_validated(self):
        config = self._config()

        publication = replace(
            config.publication,
            annotation_rules=(
                PublicationAnnotationRule(
                    predicate_iri=(
                        "https://example.org/language"
                    ),
                    object_kind="language_literal",
                    fixed_value="value",
                ),
                PublicationAnnotationRule(
                    predicate_iri=(
                        "https://example.org/typed"
                    ),
                    object_kind="typed_literal",
                    fixed_value="value",
                    language="en",
                ),
                PublicationAnnotationRule(
                    predicate_iri=(
                        "https://example.org/iri"
                    ),
                    object_kind="iri",
                    fixed_value=(
                        "https://example.org/object"
                    ),
                    datatype_iri=(
                        "https://example.org/datatype"
                    ),
                ),
            ),
        )

        config = replace(
            config,
            publication=publication,
        )

        self.assertTrue(
            {
                "annotation_language_required",
                "annotation_datatype_required",
                "annotation_language_not_allowed",
                "annotation_datatype_not_allowed",
            }.issubset(
                self._codes(config)
            )
        )

    def test_formal_only_annotation_sources_cannot_apply_to_development(
        self,
    ):
        config = self._config()

        publication = replace(
            config.publication,
            annotation_rules=(
                PublicationAnnotationRule(
                    predicate_iri=(
                        "https://example.org/released"
                    ),
                    object_kind="plain_literal",
                    applicability="both",
                    value_source=(
                        "release.release_identifier"
                    ),
                ),
            ),
        )

        config = replace(
            config,
            publication=publication,
        )

        self.assertIn(
            (
                "formal_only_annotation_source_"
                "in_development"
            ),
            self._codes(config),
        )

    def test_publication_product_text_keys_are_unique(self):
        config = self._config()

        publication = replace(
            config.publication,
            product_labels=(
                ProductText(
                    "integrated",
                    "First label",
                ),
                ProductText(
                    "integrated",
                    "Second label",
                ),
            ),
            product_descriptions=(
                ProductText(
                    "alignment",
                    "First description",
                ),
                ProductText(
                    "alignment",
                    "Second description",
                ),
            ),
        )

        config = replace(
            config,
            publication=publication,
        )

        issues = tuple(
            issue
            for issue in validate_project_config(
                config
            )
            if issue.code
            == "duplicate_publication_product_text"
        )

        self.assertEqual(
            len(issues),
            2,
        )

        self.assertEqual(
            {
                issue.path
                for issue in issues
            },
            {
                "publication.product_labels",
                "publication.product_descriptions",
            },
        )

    def test_annotation_rule_requires_configured_optional_scalar_source(
        self,
    ):
        config = self._config()

        publication = replace(
            config.publication,
            repository_iri=None,
            license_iri=None,
            development_status=None,
            annotation_rules=(
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
                        "https://example.org/license"
                    ),
                    object_kind="iri",
                    value_source=(
                        "publication.license_iri"
                    ),
                ),
                PublicationAnnotationRule(
                    predicate_iri=(
                        "https://example.org/status"
                    ),
                    object_kind="plain_literal",
                    value_source=(
                        "publication.development_status"
                    ),
                ),
            ),
        )

        config = replace(
            config,
            publication=publication,
        )

        issues = tuple(
            issue
            for issue in validate_project_config(
                config
            )
            if issue.code
            == "annotation_value_source_unavailable"
        )

        self.assertEqual(
            len(issues),
            3,
        )

    def test_annotation_product_sources_require_values_in_rule_scope(
        self,
    ):
        config = self._config()

        alignment = replace(
            config.product_graph.products[0],
            stable_ontology_iri=None,
            release_iri_pattern=None,
        )

        publication = replace(
            config.publication,
            product_descriptions=(),
            annotation_rules=(
                PublicationAnnotationRule(
                    predicate_iri=(
                        "https://example.org/label"
                    ),
                    object_kind="plain_literal",
                    value_source="product.label",
                    product_keys=(
                        "alignment",
                    ),
                ),
                PublicationAnnotationRule(
                    predicate_iri=(
                        "https://example.org/description"
                    ),
                    object_kind="plain_literal",
                    value_source=(
                        "product.description"
                    ),
                    product_keys=(
                        "alignment",
                    ),
                ),
                PublicationAnnotationRule(
                    predicate_iri=(
                        "https://example.org/stable"
                    ),
                    object_kind="iri",
                    value_source=(
                        "product.stable_ontology_iri"
                    ),
                    product_keys=(
                        "alignment",
                    ),
                ),
                PublicationAnnotationRule(
                    predicate_iri=(
                        "https://example.org/release"
                    ),
                    object_kind="iri",
                    applicability="formal",
                    value_source=(
                        "product.release_version_iri"
                    ),
                    product_keys=(
                        "alignment",
                    ),
                ),
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
            publication=publication,
        )

        issues = tuple(
            issue
            for issue in validate_project_config(
                config
            )
            if issue.code
            == "annotation_value_source_unavailable"
        )

        self.assertEqual(
            len(issues),
            4,
        )

    def test_empty_multivalued_annotation_sources_are_valid(self):
        config = self._config()

        publication = replace(
            config.publication,
            creators=(),
            contributors=(),
            annotation_rules=(
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
            ),
        )

        config = replace(
            config,
            publication=publication,
        )

        self.assertEqual(
            validate_project_config(
                config
            ),
            (),
        )

    def test_multi_product_dependency_cycle_is_reported(self):
        config = self._config()

        alignment = replace(
            config.product_graph.products[0],
            product_dependencies=(
                "integrated",
            ),
        )

        integrated = replace(
            config.product_graph.products[1],
            product_dependencies=(
                "alignment",
            ),
        )

        config = replace(
            config,
            product_graph=ProductGraph(
                products=(
                    alignment,
                    integrated,
                ),
            ),
        )

        issues = validate_project_config(config)

        cycle_issues = tuple(
            issue
            for issue in issues
            if issue.code
            == "product_dependency_cycle"
        )

        self.assertEqual(
            len(cycle_issues),
            1,
        )

        self.assertIn(
            "alignment, integrated",
            cycle_issues[0].message,
        )

    def test_self_dependency_cycle_is_reported(self):
        config = self._config()

        alignment = replace(
            config.product_graph.products[0],
            product_dependencies=(
                "alignment",
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

        self.assertIn(
            "product_dependency_cycle",
            self._codes(config),
        )

    def test_local_duplicate_bindings_are_reported(self):
        config = self._config()

        workbook = replace(
            config.workbook,
            header_bindings=(
                HeaderBinding(
                    "row_id",
                    "RowID",
                ),
                HeaderBinding(
                    "row_id",
                    "Source",
                ),
                HeaderBinding(
                    "source",
                    "Source",
                ),
            ),
        )

        source = replace(
            config.vocabularies[0],
            prefixes=(
                PrefixBinding(
                    "src",
                    "https://example.org/source/",
                ),
                PrefixBinding(
                    "src",
                    "https://example.org/alternate/",
                ),
            ),
        )

        validation = replace(
            config.validation_profiles[0],
            fixed_count_policies=(
                FixedCountPolicy(
                    "mapping-count",
                    5,
                ),
                FixedCountPolicy(
                    "mapping-count",
                    6,
                ),
            ),
        )

        config = replace(
            config,
            workbook=workbook,
            vocabularies=(
                source,
                config.vocabularies[1],
            ),
            validation_profiles=(
                validation,
            ),
        )

        self.assertTrue(
            {
                "duplicate_header_field",
                "duplicate_header_column",
                "duplicate_prefix",
                "duplicate_fixed_count_policy_key",
            }.issubset(self._codes(config))
        )

    def test_issue_order_is_canonical_and_repeatable(self):
        config = self._config()

        product = replace(
            config.product_graph.products[1],
            product_dependencies=(
                "z-missing",
                "a-missing",
            ),
            validation_profile="missing-profile",
        )

        source = replace(
            config.vocabularies[0],
            permitted_products=(
                "z-missing",
                "a-missing",
            ),
        )

        config = replace(
            config,
            vocabularies=(
                source,
                config.vocabularies[1],
            ),
            product_graph=ProductGraph(
                products=(
                    config.product_graph.products[0],
                    product,
                ),
            ),
        )

        first = validate_project_config(config)
        second = validate_project_config(config)

        self.assertEqual(
            first,
            second,
        )

        observed = tuple(
            (
                issue.path,
                issue.code,
                issue.message,
            )
            for issue in first
        )

        self.assertEqual(
            observed,
            tuple(sorted(observed)),
        )


if __name__ == "__main__":
    unittest.main()
