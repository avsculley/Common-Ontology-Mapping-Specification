import unittest

from coms.config import (
    ProductDefinition,
    ProductGraph,
    ProductImport,
)
from coms.publication import (
    PublicationError,
    development_import_iris,
    formal_import_iris,
    release_iri_pattern_issues,
    release_version_iri,
)
from coms.release_context import (
    FormalReleaseContext,
    FormalReleaseContextError,
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
