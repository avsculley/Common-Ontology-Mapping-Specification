"""Project-neutral declarative configuration model for COMS.

This module defines immutable configuration values only. It does not load
configuration files, resolve paths, inspect ontologies, or execute policy.
Those responsibilities belong to later configuration and framework layers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


VocabularyRole = Literal[
    "source",
    "target",
    "structural",
    "annotation",
]


@dataclass(frozen=True, order=True)
class PrefixBinding:
    """One prefix-to-namespace binding."""

    prefix: str
    namespace_iri: str


@dataclass(frozen=True, order=True)
class HeaderBinding:
    """Bind one framework field name to one workbook column heading."""

    field: str
    column: str


@dataclass(frozen=True, order=True)
class CatalogMapping:
    """Map one ontology IRI to one project-local catalog target."""

    ontology_iri: str
    target: str


@dataclass(frozen=True)
class WorkbookProfile:
    """Project-specific workbook shape and COMS column bindings."""

    workbook_path: str
    sheet_selectors: tuple[str, ...] = ()
    header_bindings: tuple[HeaderBinding, ...] = ()
    required_columns: tuple[str, ...] = ()
    optional_columns: tuple[str, ...] = ()
    documentation_only_columns: tuple[str, ...] = ()
    row_id_column: str = ""
    allowed_expression_types: tuple[str, ...] = ()
    explicit_blank_representation: str | None = None


@dataclass(frozen=True)
class VocabularyProfile:
    """One configured vocabulary participating in a mapping project.

    Product permit/prohibit collections are constraints. An empty collection
    imposes no constraint from that direction.
    """

    vocabulary_key: str
    role: VocabularyRole
    namespace_iris: tuple[str, ...] = ()
    prefixes: tuple[PrefixBinding, ...] = ()
    ontology_iri: str | None = None
    version_iri: str | None = None
    validation_dependency: bool = False
    catalog_mappings: tuple[CatalogMapping, ...] = ()
    permitted_products: tuple[str, ...] = ()
    prohibited_products: tuple[str, ...] = ()


@dataclass(frozen=True)
class ExpressionProfile:
    """Configured expression languages and canonicalization policy."""

    allowed_owl_predicates: tuple[str, ...] = ()
    allowed_skos_predicates: tuple[str, ...] = ()
    swrl_enabled: bool = False
    supported_complex_expression_grammar: tuple[str, ...] = ()
    annotation_policies: tuple[str, ...] = ()
    transformation_registry: tuple[str, ...] = ()
    canonicalization_version: str = ""


@dataclass(frozen=True)
class ProductDefinition:
    """Declarative definition of one generated or supporting product.

    ``product_dependencies`` contains keys of other configured products.
    ``imports`` contains ontology import declarations and is intentionally
    distinct from the product-dependency graph.

    Vocabulary permit/prohibit collections are constraints. An empty
    collection imposes no constraint from that direction.
    """

    product_key: str
    output_path: str
    product_type: str
    stable_ontology_iri: str | None = None
    release_iri_pattern: str | None = None
    imports: tuple[str, ...] = ()
    product_dependencies: tuple[str, ...] = ()
    inclusion_policy: str | None = None
    permitted_vocabularies: tuple[str, ...] = ()
    prohibited_vocabularies: tuple[str, ...] = ()
    serialization_profile: str | None = None
    validation_profile: str | None = None
    package_role: str | None = None


@dataclass(frozen=True)
class ProductGraph:
    """All products and their declared dependency relationships.

    Product tuple order is the configured project product order.
    """

    products: tuple[ProductDefinition, ...] = ()


@dataclass(frozen=True, order=True)
class FixedCountPolicy:
    """One optional named fixed-count validation baseline."""

    key: str
    expected: int


@dataclass(frozen=True)
class ValidationProfile:
    """Declarative validation policy that products may reference by key."""

    profile_key: str
    rdf_parser_checks: bool = False
    owlapi_parser_checks: bool = False
    structural_axiom_roundtrip_checks: bool = False
    annotation_preservation_checks: bool = False
    exact_product_list: tuple[str, ...] = ()
    import_policy_validation: bool = False
    catalog_validation: bool = False
    allowed_mutable_imports: tuple[str, ...] = ()
    reasoners: tuple[str, ...] = ()
    expected_consistency: bool | None = None
    permitted_unsatisfiable_classes: tuple[str, ...] = ()
    positive_entailment_tests: tuple[str, ...] = ()
    negative_entailment_tests: tuple[str, ...] = ()
    instance_data_tests: tuple[str, ...] = ()
    swrl_validation: bool = False
    fixed_count_policies: tuple[FixedCountPolicy, ...] = ()
    project_specific_validation_commands: tuple[str, ...] = ()


@dataclass(frozen=True, order=True)
class ProductText:
    """Associate publication text with a configured product."""

    product_key: str
    text: str


@dataclass(frozen=True)
class PublicationProfile:
    """Project and product publication metadata policy."""

    project_title: str
    stable_ontology_iris: tuple[str, ...] = ()
    version_iri_policy: str | None = None
    release_identifier_format: str | None = None
    repository_iri: str | None = None
    license_iri: str | None = None
    creators: tuple[str, ...] = ()
    contributors: tuple[str, ...] = ()
    development_status: str | None = None
    product_labels: tuple[ProductText, ...] = ()
    product_descriptions: tuple[ProductText, ...] = ()


@dataclass(frozen=True)
class ReleaseLayout:
    """Declarative release-package and archive layout."""

    archive_prefix: str | None = None
    package_members: tuple[str, ...] = ()
    source_artifacts: tuple[str, ...] = ()
    evidence_artifacts: tuple[str, ...] = ()
    product_artifacts: tuple[str, ...] = ()
    manifest_path: str | None = None
    checksum_path: str | None = None
    release_notes_path: str | None = None
    required_release_note_sections: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProjectConfig:
    """Complete project-neutral COMS configuration."""

    project_key: str
    project_title: str
    repository_root: str
    authoritative_mapping_source: str
    primary_output: str
    generated_warning: str
    configuration_schema_version: str
    workbook: WorkbookProfile
    vocabularies: tuple[VocabularyProfile, ...]
    expressions: ExpressionProfile
    product_graph: ProductGraph
    validation_profiles: tuple[ValidationProfile, ...]
    publication: PublicationProfile
    release_layout: ReleaseLayout
