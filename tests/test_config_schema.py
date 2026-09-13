from copy import deepcopy
import unittest

from coms.config import (
    ConfigSchemaError,
    parse_project_config,
    validate_project_config,
)


class ConfigurationSchemaTests(unittest.TestCase):
    def _mapping(self):
        return {
            "schema_version": "1",
            "project": {
                "key": "synthetic",
                "title": "Synthetic Mapping",
                "repository_root": ".",
                "authoritative_mapping_source": "workbook",
                "primary_output": "integrated",
                "generated_warning": "GENERATED FILE",
            },
            "workbook": {
                "path": "mappings/example.xlsx",
                "sheet_selectors": [
                    "Mappings",
                ],
                "header_bindings": [
                    {
                        "field": "row_id",
                        "column": "RowID",
                    },
                    {
                        "field": "source",
                        "column": "Source",
                    },
                    {
                        "field": "target",
                        "column": "Target",
                    },
                ],
                "required_columns": [
                    "RowID",
                    "Source",
                    "Target",
                ],
                "row_id_column": "RowID",
                "allowed_expression_types": [
                    "class_mapping",
                ],
            },
            "vocabularies": [
                {
                    "key": "source",
                    "role": "source",
                    "namespace_iris": [
                        "https://example.org/source/",
                    ],
                    "prefixes": [
                        {
                            "prefix": "src",
                            "namespace_iri": (
                                "https://example.org/source/"
                            ),
                        },
                    ],
                    "permitted_products": [
                        "alignment",
                        "integrated",
                    ],
                },
                {
                    "key": "target",
                    "role": "target",
                    "namespace_iris": [
                        "https://example.org/target/",
                    ],
                    "permitted_products": [
                        "integrated",
                    ],
                },
            ],
            "expressions": {
                "canonicalization_version": "synthetic-v1",
            },
            "products": [
                {
                    "key": "alignment",
                    "output_path": "build/alignment.ttl",
                    "type": "mapping",
                    "permitted_vocabularies": [
                        "source",
                    ],
                    "validation_profile": "default",
                },
                {
                    "key": "integrated",
                    "output_path": "build/integrated.ttl",
                    "type": "integrated",
                    "dependencies": [
                        "alignment",
                    ],
                    "permitted_vocabularies": [
                        "source",
                        "target",
                    ],
                    "validation_profile": "default",
                },
            ],
            "validation_profiles": [
                {
                    "key": "default",
                    "rdf_parser_checks": True,
                    "expected_consistency": True,
                    "exact_product_list": [
                        "alignment",
                        "integrated",
                    ],
                    "fixed_count_policies": [
                        {
                            "key": "mapping-count",
                            "expected": 5,
                        },
                    ],
                },
            ],
            "publication": {
                "repository_iri": (
                    "https://example.org/repository"
                ),
                "product_labels": [
                    {
                        "product_key": "integrated",
                        "text": "Integrated Mapping",
                    },
                ],
            },
            "release": {
                "archive_prefix": "synthetic-release",
                "product_artifacts": [
                    "build/integrated.ttl",
                ],
            },
        }

    def test_valid_mapping_parses_to_domain_model(self):
        config = parse_project_config(
            self._mapping()
        )

        self.assertEqual(
            config.configuration_schema_version,
            "1",
        )

        self.assertEqual(
            config.project_key,
            "synthetic",
        )

        self.assertEqual(
            config.workbook.workbook_path,
            "mappings/example.xlsx",
        )

        self.assertEqual(
            config.product_graph.products[1].product_dependencies,
            ("alignment",),
        )

        self.assertEqual(
            config.vocabularies[0].namespace_iris,
            ("https://example.org/source/",),
        )

        self.assertEqual(
            validate_project_config(config),
            (),
        )

    def test_release_configuration_may_be_omitted(self):
        data = self._mapping()
        del data["release"]

        config = parse_project_config(
            data
        )

        self.assertIsNone(
            config.release_layout.archive_prefix,
        )

        self.assertEqual(
            config.release_layout.package_members,
            (),
        )

        self.assertEqual(
            config.release_layout.product_artifacts,
            (),
        )

        self.assertEqual(
            validate_project_config(config),
            (),
        )

    def test_publication_title_defaults_to_project_title(self):
        config = parse_project_config(
            self._mapping()
        )

        self.assertEqual(
            config.publication.project_title,
            "Synthetic Mapping",
        )

    def test_array_of_table_errors_preserve_original_indices(self):
        data = self._mapping()

        data["products"] = [
            "not-a-table",
            {
                "key": "later-product",
                "output_path": 42,
                "type": "mapping",
            },
        ]

        with self.assertRaises(
            ConfigSchemaError
        ) as context:
            parse_project_config(data)

        observed = {
            (
                issue.path,
                issue.code,
            )
            for issue in context.exception.issues
        }

        self.assertIn(
            (
                "products[0]",
                "invalid_type",
            ),
            observed,
        )

        self.assertIn(
            (
                "products[1].output_path",
                "invalid_type",
            ),
            observed,
        )

        self.assertNotIn(
            (
                "products[0].output_path",
                "invalid_type",
            ),
            observed,
        )

    def test_unknown_keys_are_rejected(self):
        data = self._mapping()
        data["project"]["titel"] = "Typo"

        with self.assertRaises(
            ConfigSchemaError
        ) as context:
            parse_project_config(data)

        self.assertIn(
            "unknown_key",
            {
                issue.code
                for issue in context.exception.issues
            },
        )

        self.assertIn(
            "project.titel",
            {
                issue.path
                for issue in context.exception.issues
            },
        )

    def test_missing_required_fields_are_rejected(self):
        data = self._mapping()
        del data["project"]["key"]
        del data["products"][0]["output_path"]

        with self.assertRaises(
            ConfigSchemaError
        ) as context:
            parse_project_config(data)

        observed = {
            issue.path
            for issue in context.exception.issues
            if issue.code == "missing_key"
        }

        self.assertTrue(
            {
                "project.key",
                "products[0].output_path",
            }.issubset(observed)
        )

    def test_wrong_primitive_types_are_rejected(self):
        data = self._mapping()
        data["project"]["title"] = 42
        data["vocabularies"][0]["namespace_iris"] = (
            "not-an-array"
        )
        data["validation_profiles"][0][
            "expected_consistency"
        ] = "yes"

        with self.assertRaises(
            ConfigSchemaError
        ) as context:
            parse_project_config(data)

        observed = {
            issue.path
            for issue in context.exception.issues
            if issue.code == "invalid_type"
        }

        self.assertTrue(
            {
                "project.title",
                "vocabularies[0].namespace_iris",
                (
                    "validation_profiles[0]."
                    "expected_consistency"
                ),
            }.issubset(observed)
        )

    def test_unsupported_schema_version_is_rejected(self):
        data = self._mapping()
        data["schema_version"] = "999"

        with self.assertRaises(
            ConfigSchemaError
        ) as context:
            parse_project_config(data)

        self.assertEqual(
            tuple(
                issue.code
                for issue in context.exception.issues
            ),
            (
                "unsupported_schema_version",
            ),
        )

    def test_schema_parsing_does_not_replace_semantic_validation(self):
        data = self._mapping()
        data["vocabularies"][0]["role"] = (
            "project-defined-invalid-role"
        )

        config = parse_project_config(data)

        self.assertIn(
            "invalid_vocabulary_role",
            {
                issue.code
                for issue in validate_project_config(
                    config
                )
            },
        )

    def test_schema_issue_order_is_repeatable_and_canonical(self):
        data = self._mapping()
        data["z_unknown"] = True
        data["a_unknown"] = True
        data["project"]["title"] = 42

        def issues():
            with self.assertRaises(
                ConfigSchemaError
            ) as context:
                parse_project_config(
                    deepcopy(data)
                )

            return context.exception.issues

        first = issues()
        second = issues()

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
