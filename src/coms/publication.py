"""Project-neutral publication primitives for COMS.

This module contains deterministic publication mechanics only. Project
publication policy is supplied through COMS configuration.

The initial publication primitive is construction of immutable release
version IRIs from one configured product release-IRI pattern and one validated
formal release context.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from string import Formatter
from typing import get_args

from .config.model import (
    AnnotationObjectKind,
    ProductDefinition,
    ProductGraph,
)
from .release_context import (
    FormalReleaseContext,
    validate_formal_release_context,
)


_RELEASE_IDENTIFIER_FIELD = "release_identifier"


_ANNOTATION_OBJECT_KINDS = frozenset(
    get_args(AnnotationObjectKind)
)


@dataclass(frozen=True, order=True)
class OntologyAnnotation:
    """One ordered project-neutral ontology annotation value.

    This value object contains no project policy about which predicates should
    occur, what order they should occur in, or which configuration fields
    supply their values.
    """

    predicate_iri: str
    object_kind: AnnotationObjectKind
    value: str
    language: str | None = None
    datatype_iri: str | None = None


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


def ontology_annotation_issues(
    annotation: OntologyAnnotation,
) -> tuple[PublicationIssue, ...]:
    """Return deterministic structural issues for one ontology annotation.

    This function validates the internal term-shape contract only. It does
    not validate IRI syntax, language-tag syntax, vocabulary policy, or
    project publication policy.
    """

    issues: list[PublicationIssue] = []

    if annotation.object_kind not in _ANNOTATION_OBJECT_KINDS:
        issues.append(
            PublicationIssue(
                code="INVALID_ANNOTATION_OBJECT_KIND",
                field="ontology_annotation.object_kind",
                message=(
                    "expected one of: "
                    + ", ".join(
                        sorted(
                            _ANNOTATION_OBJECT_KINDS
                        )
                    )
                ),
            )
        )

        return tuple(issues)

    if annotation.object_kind == "iri":
        if annotation.language is not None:
            issues.append(
                PublicationIssue(
                    code="ANNOTATION_LANGUAGE_NOT_ALLOWED",
                    field="ontology_annotation.language",
                    message=(
                        "IRI objects cannot have a language tag"
                    ),
                )
            )

        if annotation.datatype_iri is not None:
            issues.append(
                PublicationIssue(
                    code="ANNOTATION_DATATYPE_NOT_ALLOWED",
                    field="ontology_annotation.datatype_iri",
                    message=(
                        "IRI objects cannot have a datatype"
                    ),
                )
            )

    elif annotation.object_kind == "plain_literal":
        if annotation.language is not None:
            issues.append(
                PublicationIssue(
                    code="ANNOTATION_LANGUAGE_NOT_ALLOWED",
                    field="ontology_annotation.language",
                    message=(
                        "plain literals cannot have a language tag"
                    ),
                )
            )

        if annotation.datatype_iri is not None:
            issues.append(
                PublicationIssue(
                    code="ANNOTATION_DATATYPE_NOT_ALLOWED",
                    field="ontology_annotation.datatype_iri",
                    message=(
                        "plain literals cannot have a datatype"
                    ),
                )
            )

    elif annotation.object_kind == "language_literal":
        if annotation.language in {
            None,
            "",
        }:
            issues.append(
                PublicationIssue(
                    code="ANNOTATION_LANGUAGE_REQUIRED",
                    field="ontology_annotation.language",
                    message=(
                        "language literals require a language tag"
                    ),
                )
            )

        if annotation.datatype_iri is not None:
            issues.append(
                PublicationIssue(
                    code="ANNOTATION_DATATYPE_NOT_ALLOWED",
                    field="ontology_annotation.datatype_iri",
                    message=(
                        "language literals cannot have a datatype"
                    ),
                )
            )

    elif annotation.object_kind == "typed_literal":
        if annotation.language is not None:
            issues.append(
                PublicationIssue(
                    code="ANNOTATION_LANGUAGE_NOT_ALLOWED",
                    field="ontology_annotation.language",
                    message=(
                        "typed literals cannot have a language tag"
                    ),
                )
            )

        if annotation.datatype_iri in {
            None,
            "",
        }:
            issues.append(
                PublicationIssue(
                    code="ANNOTATION_DATATYPE_REQUIRED",
                    field="ontology_annotation.datatype_iri",
                    message=(
                        "typed literals require a datatype IRI"
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


def render_annotation_object_turtle(
    annotation: OntologyAnnotation,
) -> str:
    """Render one annotation object as deterministic Turtle syntax.

    Predicate rendering and prefix compaction are deliberately outside this
    primitive. IRI and language-tag syntax validation also remain separate
    validation concerns.
    """

    issues = ontology_annotation_issues(
        annotation
    )

    if issues:
        raise PublicationError(
            issues
        )

    if annotation.object_kind == "iri":
        return (
            f"<{annotation.value}>"
        )

    encoded = json.dumps(
        annotation.value,
        ensure_ascii=False,
    )

    if annotation.object_kind == "plain_literal":
        return encoded

    if annotation.object_kind == "language_literal":
        assert annotation.language is not None

        return (
            encoded
            + f"@{annotation.language}"
        )

    if annotation.object_kind == "typed_literal":
        assert annotation.datatype_iri is not None

        return (
            encoded
            + f"^^<{annotation.datatype_iri}>"
        )

    raise AssertionError(
        "validated annotation has unsupported object kind"
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


def _product_import_target(
    source: ProductDefinition,
    graph: ProductGraph,
    imported_key: str,
    index: int,
) -> ProductDefinition:
    """Resolve one governed product-import reference without inference."""

    matches = tuple(
        product
        for product in graph.products
        if product.product_key == imported_key
    )

    field = (
        f"products.{source.product_key}."
        f"product_imports[{index}].product_key"
    )

    if not matches:
        raise PublicationError(
            (
                PublicationIssue(
                    code="UNKNOWN_PRODUCT_IMPORT_TARGET",
                    field=field,
                    message=(
                        "no configured product has key "
                        f"{imported_key!r}"
                    ),
                ),
            )
        )

    if len(matches) > 1:
        raise PublicationError(
            (
                PublicationIssue(
                    code="AMBIGUOUS_PRODUCT_IMPORT_TARGET",
                    field=field,
                    message=(
                        "more than one configured product "
                        f"has key {imported_key!r}"
                    ),
                ),
            )
        )

    return matches[0]


def _stable_product_import_iri(
    target: ProductDefinition,
) -> str:
    """Return one governed product's stable ontology identity."""

    value = target.stable_ontology_iri

    if value in {
        None,
        "",
    }:
        raise PublicationError(
            (
                PublicationIssue(
                    code="MISSING_STABLE_IMPORT_IDENTITY",
                    field=(
                        f"products.{target.product_key}."
                        "stable_ontology_iri"
                    ),
                    message=(
                        "governed product import requires "
                        "a stable ontology IRI"
                    ),
                ),
            )
        )

    return value


def development_import_iris(
    product: ProductDefinition,
    graph: ProductGraph,
) -> tuple[str, ...]:
    """Resolve exact development ontology imports.

    Literal ``imports`` are emitted first in configured order. Governed
    ``product_imports`` follow in configured order and always resolve to the
    imported product's stable ontology IRI.

    ``product_dependencies`` have no ontology-import semantics.
    """

    result = list(
        product.imports
    )

    for index, imported in enumerate(
        product.product_imports
    ):
        target = _product_import_target(
            product,
            graph,
            imported.product_key,
            index,
        )

        result.append(
            _stable_product_import_iri(
                target
            )
        )

    return tuple(result)


def formal_import_iris(
    product: ProductDefinition,
    graph: ProductGraph,
    context: FormalReleaseContext,
) -> tuple[str, ...]:
    """Resolve exact formal-release ontology imports.

    Literal ``imports`` are retained exactly as configured. Governed product
    imports resolve to either the target product's stable ontology IRI or its
    release version IRI according to each ``formal_target``.

    ``product_dependencies`` are intentionally ignored.
    """

    validated = validate_formal_release_context(
        context
    )

    result = list(
        product.imports
    )

    for index, imported in enumerate(
        product.product_imports
    ):
        target = _product_import_target(
            product,
            graph,
            imported.product_key,
            index,
        )

        if imported.formal_target == "stable":
            result.append(
                _stable_product_import_iri(
                    target
                )
            )
            continue

        if imported.formal_target == "release":
            result.append(
                release_version_iri(
                    target,
                    validated,
                )
            )
            continue

        raise PublicationError(
            (
                PublicationIssue(
                    code="UNSUPPORTED_PRODUCT_IMPORT_FORMAL_TARGET",
                    field=(
                        f"products.{product.product_key}."
                        f"product_imports[{index}].formal_target"
                    ),
                    message=(
                        "expected stable or release; got "
                        f"{imported.formal_target!r}"
                    ),
                ),
            )
        )

    return tuple(result)
