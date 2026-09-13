import unittest

from coms.config import ProductDefinition
from coms.publication import (
    PublicationError,
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


if __name__ == "__main__":
    unittest.main()
