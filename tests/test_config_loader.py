from pathlib import Path
from tempfile import TemporaryDirectory
import textwrap
import unittest

from coms.config import (
    ConfigLoadError,
    ConfigSchemaError,
    load_project_config,
    validate_project_config,
)


class ConfigurationLoaderTests(unittest.TestCase):
    def _toml(self) -> str:
        return textwrap.dedent(
            '''
            schema_version = "1"

            [project]
            key = "synthetic"
            title = "Synthetic Mapping"
            repository_root = "."
            authoritative_mapping_source = "workbook"
            primary_output = "integrated"
            generated_warning = "GENERATED FILE"

            [workbook]
            path = "mappings/example.xlsx"
            sheet_selectors = ["Mappings"]
            required_columns = ["RowID", "Source", "Target"]
            row_id_column = "RowID"
            allowed_expression_types = ["class_mapping"]

            [[workbook.header_bindings]]
            field = "row_id"
            column = "RowID"

            [[workbook.header_bindings]]
            field = "source"
            column = "Source"

            [[workbook.header_bindings]]
            field = "target"
            column = "Target"

            [expressions]
            canonicalization_version = "synthetic-v1"

            [[vocabularies]]
            key = "source"
            role = "source"
            namespace_iris = ["https://example.org/source/"]
            permitted_products = ["alignment", "integrated"]

            [[vocabularies.prefixes]]
            prefix = "src"
            namespace_iri = "https://example.org/source/"

            [[vocabularies]]
            key = "target"
            role = "target"
            namespace_iris = ["https://example.org/target/"]
            permitted_products = ["integrated"]

            [[products]]
            key = "alignment"
            output_path = "build/alignment.ttl"
            type = "mapping"
            permitted_vocabularies = ["source"]
            validation_profile = "default"

            [[products]]
            key = "integrated"
            output_path = "build/integrated.ttl"
            type = "integrated"
            dependencies = ["alignment"]
            permitted_vocabularies = ["source", "target"]
            validation_profile = "default"

            [[validation_profiles]]
            key = "default"
            rdf_parser_checks = true
            expected_consistency = true
            exact_product_list = ["alignment", "integrated"]

            [[validation_profiles.fixed_count_policies]]
            key = "mapping-count"
            expected = 5

            [publication]
            repository_iri = "https://example.org/repository"

            [[publication.product_labels]]
            product_key = "integrated"
            text = "Integrated Mapping"

            [release]
            archive_prefix = "synthetic-release"
            product_artifacts = ["build/integrated.ttl"]
            '''
        ).lstrip()

    def _write(
        self,
        directory: str,
        content: str,
    ) -> Path:
        path = (
            Path(directory)
            / "coms.toml"
        )

        path.write_text(
            content,
            encoding="utf-8",
        )

        return path

    def test_valid_toml_loads_to_project_config(self):
        with TemporaryDirectory() as directory:
            path = self._write(
                directory,
                self._toml(),
            )

            config = load_project_config(
                path
            )

        self.assertEqual(
            config.project_key,
            "synthetic",
        )

        self.assertEqual(
            config.product_graph.products[
                1
            ].product_dependencies,
            ("alignment",),
        )

        self.assertEqual(
            validate_project_config(
                config
            ),
            (),
        )

    def test_loader_does_not_apply_semantic_validation(self):
        text = self._toml().replace(
            'role = "source"',
            'role = "not-a-framework-role"',
            1,
        )

        with TemporaryDirectory() as directory:
            path = self._write(
                directory,
                text,
            )

            config = load_project_config(
                path
            )

        self.assertIn(
            "invalid_vocabulary_role",
            {
                issue.code
                for issue
                in validate_project_config(
                    config
                )
            },
        )

    def test_schema_errors_are_not_wrapped_as_load_errors(self):
        text = self._toml().replace(
            'title = "Synthetic Mapping"',
            'titel = "Synthetic Mapping"',
            1,
        )

        with TemporaryDirectory() as directory:
            path = self._write(
                directory,
                text,
            )

            with self.assertRaises(
                ConfigSchemaError
            ):
                load_project_config(
                    path
                )

    def test_invalid_toml_is_reported_as_load_error(self):
        with TemporaryDirectory() as directory:
            path = (
                Path(directory)
                / "broken.toml"
            )

            path.write_text(
                '[project\nkey = "broken"',
                encoding="utf-8",
            )

            with self.assertRaises(
                ConfigLoadError
            ) as context:
                load_project_config(
                    path
                )

        self.assertEqual(
            context.exception.code,
            "invalid_toml",
        )

    def test_invalid_utf8_is_reported_as_load_error(self):
        with TemporaryDirectory() as directory:
            path = (
                Path(directory)
                / "invalid-utf8.toml"
            )

            path.write_bytes(
                b'\xff\xfe\x00\x00'
            )

            with self.assertRaises(
                ConfigLoadError
            ) as context:
                load_project_config(
                    path
                )

        self.assertEqual(
            context.exception.code,
            "invalid_encoding",
        )

    def test_missing_file_is_reported_as_load_error(self):
        with TemporaryDirectory() as directory:
            path = (
                Path(directory)
                / "missing.toml"
            )

            with self.assertRaises(
                ConfigLoadError
            ) as context:
                load_project_config(
                    path
                )

        self.assertEqual(
            context.exception.code,
            "read_error",
        )

        self.assertEqual(
            context.exception.path,
            str(path),
        )


if __name__ == "__main__":
    unittest.main()
