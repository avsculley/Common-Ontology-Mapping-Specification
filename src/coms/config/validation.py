"""Pure structural validation for COMS project configuration.

Validation in this module operates only on declarative configuration values.
It does not resolve paths, inspect files, load ontologies, or execute project
tools. Runtime and filesystem validation belong to later framework layers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, get_args

from .model import (
    ProductDefinition,
    ProductImportFormalTarget,
    ProjectConfig,
    VocabularyRole,
)


_VOCABULARY_ROLES = frozenset(
    get_args(VocabularyRole)
)

_PRODUCT_IMPORT_FORMAL_TARGETS = frozenset(
    get_args(ProductImportFormalTarget)
)


@dataclass(frozen=True)
class ConfigIssue:
    """One deterministic configuration-validation issue."""

    code: str
    path: str
    message: str


def _duplicate_values(values: Iterable[str]) -> tuple[str, ...]:
    counts: dict[str, int] = {}

    for value in values:
        counts[value] = counts.get(value, 0) + 1

    return tuple(
        sorted(
            value
            for value, count in counts.items()
            if count > 1
        )
    )


def _sorted_issues(
    issues: Iterable[ConfigIssue],
) -> tuple[ConfigIssue, ...]:
    return tuple(
        sorted(
            issues,
            key=lambda issue: (
                issue.path,
                issue.code,
                issue.message,
            ),
        )
    )


def _cyclic_product_components(
    products: tuple[ProductDefinition, ...],
) -> tuple[tuple[str, ...], ...]:
    """Return deterministic strongly connected cyclic components."""

    keys = tuple(
        product.product_key
        for product in products
    )

    if _duplicate_values(keys):
        # A keyed graph is ambiguous until duplicate keys are repaired.
        return ()

    key_set = set(keys)

    graph = {
        product.product_key: tuple(
            sorted(
                {
                    dependency
                    for dependency in product.product_dependencies
                    if dependency in key_set
                }
            )
        )
        for product in products
    }

    index = 0
    indices: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    cyclic_components: list[tuple[str, ...]] = []

    def visit(node: str) -> None:
        nonlocal index

        indices[node] = index
        lowlinks[node] = index
        index += 1

        stack.append(node)
        on_stack.add(node)

        for dependency in graph[node]:
            if dependency not in indices:
                visit(dependency)
                lowlinks[node] = min(
                    lowlinks[node],
                    lowlinks[dependency],
                )
            elif dependency in on_stack:
                lowlinks[node] = min(
                    lowlinks[node],
                    indices[dependency],
                )

        if lowlinks[node] != indices[node]:
            return

        component: list[str] = []

        while True:
            member = stack.pop()
            on_stack.remove(member)
            component.append(member)

            if member == node:
                break

        ordered = tuple(sorted(component))

        if len(ordered) > 1:
            cyclic_components.append(ordered)
        elif node in graph[node]:
            cyclic_components.append(ordered)

    for node in sorted(graph):
        if node not in indices:
            visit(node)

    return tuple(sorted(cyclic_components))


def validate_project_config(
    config: ProjectConfig,
) -> tuple[ConfigIssue, ...]:
    """Validate project-neutral structural configuration semantics.

    The returned tuple is canonically ordered and therefore stable across
    repeated validation runs.
    """

    issues: list[ConfigIssue] = []

    products = config.product_graph.products

    product_keys = {
        product.product_key
        for product in products
    }

    duplicate_product_keys = _duplicate_values(
        product.product_key
        for product in products
    )

    vocabulary_keys = {
        vocabulary.vocabulary_key
        for vocabulary in config.vocabularies
    }

    validation_profile_keys = {
        profile.profile_key
        for profile in config.validation_profiles
    }

    # ------------------------------------------------------------------
    # Unique top-level keys
    # ------------------------------------------------------------------

    for key in _duplicate_values(
        vocabulary.vocabulary_key
        for vocabulary in config.vocabularies
    ):
        issues.append(
            ConfigIssue(
                code="duplicate_vocabulary_key",
                path="vocabularies",
                message=(
                    "duplicate vocabulary key: "
                    f"{key}"
                ),
            )
        )

    for key in duplicate_product_keys:
        issues.append(
            ConfigIssue(
                code="duplicate_product_key",
                path="product_graph.products",
                message=(
                    "duplicate product key: "
                    f"{key}"
                ),
            )
        )

    for key in _duplicate_values(
        profile.profile_key
        for profile in config.validation_profiles
    ):
        issues.append(
            ConfigIssue(
                code="duplicate_validation_profile_key",
                path="validation_profiles",
                message=(
                    "duplicate validation profile key: "
                    f"{key}"
                ),
            )
        )

    # ------------------------------------------------------------------
    # Workbook bindings
    # ------------------------------------------------------------------

    for field in _duplicate_values(
        binding.field
        for binding in config.workbook.header_bindings
    ):
        issues.append(
            ConfigIssue(
                code="duplicate_header_field",
                path="workbook.header_bindings",
                message=(
                    "framework field is bound more than once: "
                    f"{field}"
                ),
            )
        )

    for column in _duplicate_values(
        binding.column
        for binding in config.workbook.header_bindings
    ):
        issues.append(
            ConfigIssue(
                code="duplicate_header_column",
                path="workbook.header_bindings",
                message=(
                    "workbook column is bound more than once: "
                    f"{column}"
                ),
            )
        )

    # ------------------------------------------------------------------
    # Vocabulary configuration
    # ------------------------------------------------------------------

    for vocabulary in config.vocabularies:
        path = (
            "vocabularies"
            f"[{vocabulary.vocabulary_key}]"
        )

        if vocabulary.role not in _VOCABULARY_ROLES:
            issues.append(
                ConfigIssue(
                    code="invalid_vocabulary_role",
                    path=f"{path}.role",
                    message=(
                        "invalid vocabulary role: "
                        f"{vocabulary.role}"
                    ),
                )
            )

        for prefix in _duplicate_values(
            binding.prefix
            for binding in vocabulary.prefixes
        ):
            issues.append(
                ConfigIssue(
                    code="duplicate_prefix",
                    path=f"{path}.prefixes",
                    message=(
                        "prefix is bound more than once: "
                        f"{prefix}"
                    ),
                )
            )

        for field_name, references in (
            (
                "permitted_products",
                vocabulary.permitted_products,
            ),
            (
                "prohibited_products",
                vocabulary.prohibited_products,
            ),
        ):
            for reference in sorted(set(references)):
                if reference not in product_keys:
                    issues.append(
                        ConfigIssue(
                            code="unknown_product_reference",
                            path=f"{path}.{field_name}",
                            message=(
                                "unknown product key: "
                                f"{reference}"
                            ),
                        )
                    )

        for reference in sorted(
            set(vocabulary.permitted_products)
            & set(vocabulary.prohibited_products)
        ):
            issues.append(
                ConfigIssue(
                    code="contradictory_product_constraint",
                    path=path,
                    message=(
                        "product is both permitted and prohibited: "
                        f"{reference}"
                    ),
                )
            )

    # ------------------------------------------------------------------
    # Product graph references and constraints
    # ------------------------------------------------------------------

    for product in products:
        path = (
            "product_graph.products"
            f"[{product.product_key}]"
        )

        for imported_key in _duplicate_values(
            value.product_key
            for value in product.product_imports
        ):
            issues.append(
                ConfigIssue(
                    code="duplicate_product_import",
                    path=f"{path}.product_imports",
                    message=(
                        "product is imported more than once: "
                        f"{imported_key}"
                    ),
                )
            )

        for index, imported in enumerate(
            product.product_imports
        ):
            import_path = (
                f"{path}.product_imports[{index}]"
            )

            if imported.product_key not in product_keys:
                issues.append(
                    ConfigIssue(
                        code="unknown_product_import",
                        path=f"{import_path}.product_key",
                        message=(
                            "unknown imported product key: "
                            f"{imported.product_key}"
                        ),
                    )
                )

            if (
                imported.formal_target
                not in _PRODUCT_IMPORT_FORMAL_TARGETS
            ):
                issues.append(
                    ConfigIssue(
                        code="invalid_product_import_formal_target",
                        path=f"{import_path}.formal_target",
                        message=(
                            "expected one of: "
                            + ", ".join(
                                sorted(
                                    _PRODUCT_IMPORT_FORMAL_TARGETS
                                )
                            )
                        ),
                    )
                )

        for dependency in sorted(
            set(product.product_dependencies)
        ):
            if dependency not in product_keys:
                issues.append(
                    ConfigIssue(
                        code="unknown_product_dependency",
                        path=f"{path}.product_dependencies",
                        message=(
                            "unknown product dependency: "
                            f"{dependency}"
                        ),
                    )
                )

        for field_name, references in (
            (
                "permitted_vocabularies",
                product.permitted_vocabularies,
            ),
            (
                "prohibited_vocabularies",
                product.prohibited_vocabularies,
            ),
        ):
            for reference in sorted(set(references)):
                if reference not in vocabulary_keys:
                    issues.append(
                        ConfigIssue(
                            code="unknown_vocabulary_reference",
                            path=f"{path}.{field_name}",
                            message=(
                                "unknown vocabulary key: "
                                f"{reference}"
                            ),
                        )
                    )

        for reference in sorted(
            set(product.permitted_vocabularies)
            & set(product.prohibited_vocabularies)
        ):
            issues.append(
                ConfigIssue(
                    code="contradictory_vocabulary_constraint",
                    path=path,
                    message=(
                        "vocabulary is both permitted and prohibited: "
                        f"{reference}"
                    ),
                )
            )

        if (
            product.validation_profile is not None
            and product.validation_profile
            not in validation_profile_keys
        ):
            issues.append(
                ConfigIssue(
                    code="unknown_validation_profile",
                    path=f"{path}.validation_profile",
                    message=(
                        "unknown validation profile key: "
                        f"{product.validation_profile}"
                    ),
                )
            )

    # ------------------------------------------------------------------
    # Explicit cross-direction vocabulary/product contradictions
    # ------------------------------------------------------------------
    #
    # Permit/prohibit constraints exist on both configuration surfaces.
    # Broader inclusion semantics remain project-specific: in particular,
    # omission from a non-empty permit list is not interpreted here.
    #
    # The generic model can, however, reject an explicit positive statement
    # on one side that is explicitly denied on the other side.
    #
    # Skip this reconciliation when keys are duplicated because the keyed
    # relationship is ambiguous until those primary errors are repaired.

    duplicate_vocabulary_keys = _duplicate_values(
        vocabulary.vocabulary_key
        for vocabulary in config.vocabularies
    )

    if not duplicate_product_keys and not duplicate_vocabulary_keys:
        products_by_key = {
            product.product_key: product
            for product in products
        }

        vocabularies_by_key = {
            vocabulary.vocabulary_key: vocabulary
            for vocabulary in config.vocabularies
        }

        for vocabulary_key in sorted(vocabularies_by_key):
            vocabulary = vocabularies_by_key[vocabulary_key]

            for product_key in sorted(products_by_key):
                product = products_by_key[product_key]

                if (
                    product_key
                    in vocabulary.permitted_products
                    and vocabulary_key
                    in product.prohibited_vocabularies
                ):
                    issues.append(
                        ConfigIssue(
                            code="cross_constraint_conflict",
                            path=(
                                "vocabulary_product_constraints"
                                f"[{vocabulary_key},{product_key}]"
                            ),
                            message=(
                                "vocabulary explicitly permits product "
                                "while product explicitly prohibits "
                                "vocabulary"
                            ),
                        )
                    )

                if (
                    product_key
                    in vocabulary.prohibited_products
                    and vocabulary_key
                    in product.permitted_vocabularies
                ):
                    issues.append(
                        ConfigIssue(
                            code="cross_constraint_conflict",
                            path=(
                                "vocabulary_product_constraints"
                                f"[{vocabulary_key},{product_key}]"
                            ),
                            message=(
                                "vocabulary explicitly prohibits product "
                                "while product explicitly permits "
                                "vocabulary"
                            ),
                        )
                    )

    # ------------------------------------------------------------------
    # Governed product-import publication identities
    # ------------------------------------------------------------------
    #
    # Every governed product import resolves to the imported product's stable
    # ontology IRI during development publication. Formal publication either
    # retains that stable identity or resolves to the imported product's
    # configured release-version IRI.
    #
    # Skip keyed target reconciliation when duplicate product keys make the
    # target identity ambiguous.

    if not duplicate_product_keys:
        products_by_key = {
            product.product_key: product
            for product in products
        }

        imported_product_keys = {
            imported.product_key
            for product in products
            for imported in product.product_imports
            if imported.product_key in products_by_key
        }

        release_import_product_keys = {
            imported.product_key
            for product in products
            for imported in product.product_imports
            if (
                imported.product_key in products_by_key
                and imported.formal_target == "release"
            )
        }

        for imported_key in sorted(
            imported_product_keys
        ):
            target = products_by_key[
                imported_key
            ]

            if target.stable_ontology_iri in {
                None,
                "",
            }:
                issues.append(
                    ConfigIssue(
                        code=(
                            "product_import_target_missing_"
                            "stable_ontology_iri"
                        ),
                        path=(
                            "product_graph.products"
                            f"[{imported_key}]."
                            "stable_ontology_iri"
                        ),
                        message=(
                            "product is referenced by "
                            "product_imports but has no "
                            "stable ontology IRI"
                        ),
                    )
                )

        for imported_key in sorted(
            release_import_product_keys
        ):
            target = products_by_key[
                imported_key
            ]

            if target.release_iri_pattern in {
                None,
                "",
            }:
                issues.append(
                    ConfigIssue(
                        code=(
                            "product_import_target_missing_"
                            "release_iri_pattern"
                        ),
                        path=(
                            "product_graph.products"
                            f"[{imported_key}]."
                            "release_iri_pattern"
                        ),
                        message=(
                            "product is formally imported "
                            "by release identity but has no "
                            "release IRI pattern"
                        ),
                    )
                )

    for component in _cyclic_product_components(products):
        issues.append(
            ConfigIssue(
                code="product_dependency_cycle",
                path="product_graph",
                message=(
                    "cyclic product dependency component: "
                    + ", ".join(component)
                ),
            )
        )

    # ------------------------------------------------------------------
    # Validation profiles
    # ------------------------------------------------------------------

    for profile in config.validation_profiles:
        path = (
            "validation_profiles"
            f"[{profile.profile_key}]"
        )

        for key in _duplicate_values(
            policy.key
            for policy in profile.fixed_count_policies
        ):
            issues.append(
                ConfigIssue(
                    code="duplicate_fixed_count_policy_key",
                    path=f"{path}.fixed_count_policies",
                    message=(
                        "duplicate fixed-count policy key: "
                        f"{key}"
                    ),
                )
            )

        for product_key in sorted(
            set(profile.exact_product_list)
        ):
            if product_key not in product_keys:
                issues.append(
                    ConfigIssue(
                        code="unknown_validation_product",
                        path=f"{path}.exact_product_list",
                        message=(
                            "unknown product key: "
                            f"{product_key}"
                        ),
                    )
                )

    # ------------------------------------------------------------------
    # Publication product references
    # ------------------------------------------------------------------

    for field_name, entries in (
        (
            "product_labels",
            config.publication.product_labels,
        ),
        (
            "product_descriptions",
            config.publication.product_descriptions,
        ),
    ):
        for entry in entries:
            if entry.product_key not in product_keys:
                issues.append(
                    ConfigIssue(
                        code="unknown_publication_product",
                        path=(
                            "publication."
                            f"{field_name}"
                        ),
                        message=(
                            "unknown product key: "
                            f"{entry.product_key}"
                        ),
                    )
                )

    return _sorted_issues(issues)
