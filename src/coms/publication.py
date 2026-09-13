"""Project-neutral publication primitives for COMS.

This module contains deterministic publication mechanics only. Project
publication policy is supplied through COMS configuration.

The initial publication primitive is construction of immutable release
version IRIs from one configured product release-IRI pattern and one validated
formal release context.
"""

from __future__ import annotations

from dataclasses import dataclass
from string import Formatter

from .config.model import ProductDefinition
from .release_context import (
    FormalReleaseContext,
    validate_formal_release_context,
)


_RELEASE_IDENTIFIER_FIELD = "release_identifier"


@dataclass(frozen=True, order=True)
class PublicationIssue:
    """One deterministic publication-policy issue."""

    code: str
    field: str
    message: str


class PublicationError(ValueError):
    """Raised when configured publication policy cannot be applied."""

    def __init__(
        self,
        issues: tuple[PublicationIssue, ...],
    ) -> None:
        ordered = tuple(
            sorted(
                issues,
                key=lambda issue: (
                    issue.code,
                    issue.field,
                    issue.message,
                ),
            )
        )

        self.issues = ordered

        super().__init__(
            "\n".join(
                f"{issue.code}: "
                f"{issue.field}: "
                f"{issue.message}"
                for issue in ordered
            )
        )


def _pattern_field(
    product: ProductDefinition,
) -> str:
    return (
        f"products.{product.product_key}."
        "release_iri_pattern"
    )


def release_iri_pattern_issues(
    product: ProductDefinition,
) -> tuple[PublicationIssue, ...]:
    """Return deterministic issues for one configured release-IRI pattern.

    A COMS release-IRI pattern is the complete desired version IRI template.
    It must contain exactly one unformatted ``{release_identifier}``
    replacement field. No other replacement fields are framework-defined.
    """

    field = _pattern_field(product)
    pattern = product.release_iri_pattern

    if pattern is None or pattern == "":
        return (
            PublicationIssue(
                code="MISSING_RELEASE_IRI_PATTERN",
                field=field,
                message=(
                    "formal publication requires a "
                    "release_iri_pattern"
                ),
            ),
        )

    try:
        parsed = tuple(
            Formatter().parse(pattern)
        )
    except ValueError as exc:
        return (
            PublicationIssue(
                code="MALFORMED_RELEASE_IRI_PATTERN",
                field=field,
                message=str(exc),
            ),
        )

    issues: list[PublicationIssue] = []
    release_identifier_count = 0

    for (
        _literal,
        field_name,
        format_spec,
        conversion,
    ) in parsed:
        if field_name is None:
            continue

        if field_name != _RELEASE_IDENTIFIER_FIELD:
            issues.append(
                PublicationIssue(
                    code="UNSUPPORTED_RELEASE_IRI_FIELD",
                    field=field,
                    message=(
                        "unsupported replacement field: "
                        f"{field_name}"
                    ),
                )
            )
            continue

        release_identifier_count += 1

        if format_spec:
            issues.append(
                PublicationIssue(
                    code=(
                        "UNSUPPORTED_RELEASE_IRI_FORMATTING"
                    ),
                    field=field,
                    message=(
                        "release_identifier does not "
                        "support a format specification"
                    ),
                )
            )

        if conversion:
            issues.append(
                PublicationIssue(
                    code=(
                        "UNSUPPORTED_RELEASE_IRI_CONVERSION"
                    ),
                    field=field,
                    message=(
                        "release_identifier does not "
                        "support a conversion"
                    ),
                )
            )

    if release_identifier_count != 1:
        issues.append(
            PublicationIssue(
                code=(
                    "RELEASE_IDENTIFIER_PLACEHOLDER_COUNT"
                ),
                field=field,
                message=(
                    "release_iri_pattern must contain "
                    "exactly one {release_identifier} "
                    "replacement field"
                ),
            )
        )

    return tuple(
        sorted(
            set(issues),
            key=lambda issue: (
                issue.code,
                issue.field,
                issue.message,
            ),
        )
    )


def release_version_iri(
    product: ProductDefinition,
    context: FormalReleaseContext,
) -> str:
    """Build one deterministic immutable product version IRI.

    Formal release context validation remains authoritative in
    ``coms.release_context``. This function does not validate IRI syntax or
    dereference any resource.
    """

    validated = validate_formal_release_context(
        context
    )

    issues = release_iri_pattern_issues(
        product
    )

    if issues:
        raise PublicationError(
            issues
        )

    pattern = product.release_iri_pattern

    assert pattern is not None

    return pattern.format(
        release_identifier=(
            validated.release_identifier
        )
    )
