from dataclasses import FrozenInstanceError
import unittest

from coms.config import (
    ExpressionProfile,
    HeaderBinding,
    PrefixBinding,
    ProductDefinition,
    ProductGraph,
    ProductImport,
    ProjectConfig,
    PublicationProfile,
    ReleaseLayout,
    ValidationProfile,
    VocabularyProfile,
    WorkbookProfile,
)


class ConfigurationModelTests(unittest.TestCase):
    def _synthetic_config(self) -> ProjectConfig:
        workbook = WorkbookProfile(
            workbook_path="mappings/example.xlsx",
            sheet_selectors=("Classes", "Properties"),
            header_bindings=(
                HeaderBinding("row_id", "coms:RowID"),
                HeaderBinding("source", "Source"),
                HeaderBinding("target", "Target"),
            ),
            required_columns=("coms:RowID", "Source", "Target"),
            row_id_column="coms:RowID",
            allowed_expression_types=(
                "class_mapping",
                "object_property_mapping",
            ),
            explicit_blank_representation="",
        )

        source = VocabularyProfile(
            vocabulary_key="source-vocabulary",
            role="source",
            namespace_iris=("https://example.org/source/",),
            prefixes=(
                PrefixBinding(
                    "src",
                    "https://example.org/source/",
                ),
            ),
            ontology_iri="https://example.org/source",
            permitted_products=(
                "alignment",
                "integrated",
            ),
        )

        target_alpha = VocabularyProfile(
            vocabulary_key="target-alpha",
            role="target",
            namespace_iris=("https://example.org/target-a/",),
            prefixes=(
                PrefixBinding(
                    "ta",
                    "https://example.org/target-a/",
                ),
            ),
            ontology_iri="https://example.org/target-a",
            permitted_products=(
                "target-a",
                "integrated",
            ),
        )

        target_beta = VocabularyProfile(
            vocabulary_key="target-beta",
            role="target",
            namespace_iris=("https://example.org/target-b/",),
            prefixes=(
                PrefixBinding(
                    "tb",
                    "https://example.org/target-b/",
                ),
            ),
            ontology_iri="https://example.org/target-b",
            permitted_products=(
                "target-b",
                "integrated",
            ),
        )

        products = ProductGraph(
            products=(
                ProductDefinition(
                    product_key="alignment",
                    output_path="build/alignment.ttl",
                    product_type="mapping",
                    stable_ontology_iri="https://example.org/alignment",
                ),
                ProductDefinition(
                    product_key="target-a",
                    output_path="build/target-a.ttl",
                    product_type="mapping",
                    product_dependencies=("alignment",),
                    permitted_vocabularies=("target-alpha",),
                ),
                ProductDefinition(
                    product_key="target-b",
                    output_path="build/target-b.ttl",
                    product_type="mapping",
                    product_dependencies=("alignment",),
                    permitted_vocabularies=("target-beta",),
                ),
                ProductDefinition(
                    product_key="integrated",
                    output_path="build/integrated.ttl",
                    product_type="integrated",
                    product_dependencies=(
                        "target-a",
                        "target-b",
                    ),
                ),
            )
        )

        return ProjectConfig(
            project_key="synthetic-mapping",
            project_title="Synthetic Mapping Project",
            repository_root=".",
            authoritative_mapping_source="workbook",
            primary_output="integrated",
            generated_warning="GENERATED FILE",
            configuration_schema_version="1",
            workbook=workbook,
            vocabularies=(
                source,
                target_alpha,
                target_beta,
            ),
            expressions=ExpressionProfile(
                allowed_owl_predicates=(
                    "http://www.w3.org/2000/01/rdf-schema#subClassOf",
                ),
                canonicalization_version="synthetic-v1",
            ),
            product_graph=products,
            validation_profiles=(
                ValidationProfile(
                    profile_key="default",
                    rdf_parser_checks=True,
                    owlapi_parser_checks=True,
                    expected_consistency=True,
                    instance_data_tests=(
                        "tests/fixtures/synthetic-instances.ttl",
                    ),
                ),
            ),
            publication=PublicationProfile(
                project_title="Synthetic Mapping Project",
                repository_iri="https://example.org/repository",
            ),
            release_layout=ReleaseLayout(
                archive_prefix="synthetic-release",
                product_artifacts=(
                    "build/integrated.ttl",
                ),
            ),
        )

    def test_configuration_is_frozen(self):
        config = self._synthetic_config()

        with self.assertRaises(FrozenInstanceError):
            config.project_key = "changed"

    def test_multiple_source_and_target_vocabularies_are_data(self):
        config = self._synthetic_config()

        self.assertEqual(
            tuple(
                vocabulary.role
                for vocabulary in config.vocabularies
            ),
            (
                "source",
                "target",
                "target",
            ),
        )

        self.assertEqual(
            tuple(
                vocabulary.vocabulary_key
                for vocabulary in config.vocabularies
            ),
            (
                "source-vocabulary",
                "target-alpha",
                "target-beta",
            ),
        )

    def test_product_graph_supports_layered_and_parallel_products(self):
        config = self._synthetic_config()

        products = {
            product.product_key: product
            for product in config.product_graph.products
        }

        self.assertEqual(
            products["target-a"].product_dependencies,
            ("alignment",),
        )

        self.assertEqual(
            products["target-b"].product_dependencies,
            ("alignment",),
        )

        self.assertEqual(
            products["integrated"].product_dependencies,
            (
                "target-a",
                "target-b",
            ),
        )

    def test_instance_data_validation_is_project_configuration(self):
        config = self._synthetic_config()

        self.assertEqual(
            config.validation_profiles[0].instance_data_tests,
            ("tests/fixtures/synthetic-instances.ttl",),
        )

    def test_product_imports_are_distinct_from_product_dependencies(self):
        product = ProductDefinition(
            product_key="consumer",
            output_path="build/consumer.ttl",
            product_type="mapping",
            imports=(
                "https://example.org/external",
            ),
            product_imports=(
                ProductImport(
                    product_key="published-upstream",
                    formal_target="release",
                ),
            ),
            product_dependencies=(
                "build-helper",
            ),
        )

        self.assertEqual(
            product.imports,
            (
                "https://example.org/external",
            ),
        )

        self.assertEqual(
            product.product_imports[0].product_key,
            "published-upstream",
        )

        self.assertEqual(
            product.product_imports[0].formal_target,
            "release",
        )

        self.assertEqual(
            product.product_dependencies,
            (
                "build-helper",
            ),
        )

    def test_product_policy_uses_configuration_keys_not_framework_categories(
        self,
    ):
        config = self._synthetic_config()
        products = config.product_graph.products

        self.assertEqual(
            products[1].permitted_vocabularies,
            ("target-alpha",),
        )

        self.assertEqual(
            products[2].permitted_vocabularies,
            ("target-beta",),
        )


if __name__ == "__main__":
    unittest.main()
