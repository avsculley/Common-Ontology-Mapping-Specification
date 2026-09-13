"""External configuration schema parsing for COMS.

The schema is intentionally distinct from the Python dataclass layout.
Parsing validates external shape and primitive types only. Cross-reference
and project-policy semantics remain the responsibility of
``validate_project_config``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from .model import (
    CatalogMapping,
    ExpressionProfile,
    FixedCountPolicy,
    HeaderBinding,
    PrefixBinding,
    ProductDefinition,
    ProductGraph,
    ProductText,
    ProjectConfig,
    PublicationProfile,
    ReleaseLayout,
    ValidationProfile,
    VocabularyProfile,
    WorkbookProfile,
)


SUPPORTED_CONFIGURATION_SCHEMA_VERSION = "1"


@dataclass(frozen=True)
class ConfigSchemaIssue:
    """One deterministic external-schema parsing issue."""

    code: str
    path: str
    message: str


class ConfigSchemaError(ValueError):
    """Raised when external configuration does not conform to the schema."""

    def __init__(
        self,
        issues: Sequence[ConfigSchemaIssue],
    ) -> None:
        ordered = tuple(
            sorted(
                issues,
                key=lambda issue: (
                    issue.path,
                    issue.code,
                    issue.message,
                ),
            )
        )

        self.issues = ordered

        super().__init__(
            "\n".join(
                f"{issue.path}: "
                f"{issue.code}: "
                f"{issue.message}"
                for issue in ordered
            )
        )


class _SchemaParser:
    def __init__(self) -> None:
        self.issues: list[ConfigSchemaIssue] = []

    def issue(
        self,
        code: str,
        path: str,
        message: str,
    ) -> None:
        self.issues.append(
            ConfigSchemaIssue(
                code=code,
                path=path,
                message=message,
            )
        )

    def check_keys(
        self,
        table: Mapping[str, Any],
        path: str,
        allowed: set[str],
    ) -> None:
        for key in sorted(
            key
            for key in table
            if key not in allowed
        ):
            self.issue(
                "unknown_key",
                f"{path}.{key}" if path else key,
                f"unknown configuration key: {key}",
            )

    def table(
        self,
        table: Mapping[str, Any],
        key: str,
        path: str,
        *,
        required: bool = False,
    ) -> Mapping[str, Any]:
        if key not in table:
            if required:
                self.issue(
                    "missing_key",
                    path,
                    f"missing required table: {key}",
                )
            return {}

        value = table[key]

        if not isinstance(value, Mapping):
            self.issue(
                "invalid_type",
                path,
                "expected table",
            )
            return {}

        return value

    def table_array(
        self,
        table: Mapping[str, Any],
        key: str,
        path: str,
        *,
        required: bool = False,
    ) -> tuple[tuple[int, Mapping[str, Any]], ...]:
        if key not in table:
            if required:
                self.issue(
                    "missing_key",
                    path,
                    f"missing required array: {key}",
                )
            return ()

        value = table[key]

        if (
            not isinstance(value, Sequence)
            or isinstance(
                value,
                (str, bytes, bytearray),
            )
        ):
            self.issue(
                "invalid_type",
                path,
                "expected array of tables",
            )
            return ()

        result: list[
            tuple[int, Mapping[str, Any]]
        ] = []

        for index, entry in enumerate(value):
            entry_path = f"{path}[{index}]"

            if not isinstance(entry, Mapping):
                self.issue(
                    "invalid_type",
                    entry_path,
                    "expected table",
                )
                continue

            result.append(
                (
                    index,
                    entry,
                )
            )

        return tuple(result)

    def string(
        self,
        table: Mapping[str, Any],
        key: str,
        path: str,
        *,
        required: bool = False,
        default: str = "",
    ) -> str:
        if key not in table:
            if required:
                self.issue(
                    "missing_key",
                    path,
                    f"missing required key: {key}",
                )
            return default

        value = table[key]

        if not isinstance(value, str):
            self.issue(
                "invalid_type",
                path,
                "expected string",
            )
            return default

        return value

    def optional_string(
        self,
        table: Mapping[str, Any],
        key: str,
        path: str,
    ) -> str | None:
        if key not in table:
            return None

        value = table[key]

        if not isinstance(value, str):
            self.issue(
                "invalid_type",
                path,
                "expected string",
            )
            return None

        return value

    def boolean(
        self,
        table: Mapping[str, Any],
        key: str,
        path: str,
        *,
        default: bool = False,
    ) -> bool:
        if key not in table:
            return default

        value = table[key]

        if not isinstance(value, bool):
            self.issue(
                "invalid_type",
                path,
                "expected boolean",
            )
            return default

        return value

    def optional_boolean(
        self,
        table: Mapping[str, Any],
        key: str,
        path: str,
    ) -> bool | None:
        if key not in table:
            return None

        value = table[key]

        if not isinstance(value, bool):
            self.issue(
                "invalid_type",
                path,
                "expected boolean",
            )
            return None

        return value

    def integer(
        self,
        table: Mapping[str, Any],
        key: str,
        path: str,
        *,
        required: bool = False,
        default: int = 0,
    ) -> int:
        if key not in table:
            if required:
                self.issue(
                    "missing_key",
                    path,
                    f"missing required key: {key}",
                )
            return default

        value = table[key]

        if (
            not isinstance(value, int)
            or isinstance(value, bool)
        ):
            self.issue(
                "invalid_type",
                path,
                "expected integer",
            )
            return default

        return value

    def string_tuple(
        self,
        table: Mapping[str, Any],
        key: str,
        path: str,
    ) -> tuple[str, ...]:
        if key not in table:
            return ()

        value = table[key]

        if (
            not isinstance(value, Sequence)
            or isinstance(
                value,
                (str, bytes, bytearray),
            )
        ):
            self.issue(
                "invalid_type",
                path,
                "expected array of strings",
            )
            return ()

        result: list[str] = []

        for index, entry in enumerate(value):
            if not isinstance(entry, str):
                self.issue(
                    "invalid_type",
                    f"{path}[{index}]",
                    "expected string",
                )
                continue

            result.append(entry)

        return tuple(result)


def _parse_header_bindings(
    parser: _SchemaParser,
    workbook: Mapping[str, Any],
) -> tuple[HeaderBinding, ...]:
    result: list[HeaderBinding] = []

    for index, entry in parser.table_array(
        workbook,
        "header_bindings",
        "workbook.header_bindings",
    ):
        path = f"workbook.header_bindings[{index}]"

        parser.check_keys(
            entry,
            path,
            {
                "field",
                "column",
            },
        )

        result.append(
            HeaderBinding(
                field=parser.string(
                    entry,
                    "field",
                    f"{path}.field",
                    required=True,
                ),
                column=parser.string(
                    entry,
                    "column",
                    f"{path}.column",
                    required=True,
                ),
            )
        )

    return tuple(result)


def _parse_prefixes(
    parser: _SchemaParser,
    vocabulary: Mapping[str, Any],
    path: str,
) -> tuple[PrefixBinding, ...]:
    result: list[PrefixBinding] = []

    for index, entry in parser.table_array(
        vocabulary,
        "prefixes",
        f"{path}.prefixes",
    ):
        entry_path = f"{path}.prefixes[{index}]"

        parser.check_keys(
            entry,
            entry_path,
            {
                "prefix",
                "namespace_iri",
            },
        )

        result.append(
            PrefixBinding(
                prefix=parser.string(
                    entry,
                    "prefix",
                    f"{entry_path}.prefix",
                    required=True,
                ),
                namespace_iri=parser.string(
                    entry,
                    "namespace_iri",
                    f"{entry_path}.namespace_iri",
                    required=True,
                ),
            )
        )

    return tuple(result)


def _parse_catalog_mappings(
    parser: _SchemaParser,
    vocabulary: Mapping[str, Any],
    path: str,
) -> tuple[CatalogMapping, ...]:
    result: list[CatalogMapping] = []

    for index, entry in parser.table_array(
        vocabulary,
        "catalog_mappings",
        f"{path}.catalog_mappings",
    ):
        entry_path = (
            f"{path}.catalog_mappings[{index}]"
        )

        parser.check_keys(
            entry,
            entry_path,
            {
                "ontology_iri",
                "target",
            },
        )

        result.append(
            CatalogMapping(
                ontology_iri=parser.string(
                    entry,
                    "ontology_iri",
                    f"{entry_path}.ontology_iri",
                    required=True,
                ),
                target=parser.string(
                    entry,
                    "target",
                    f"{entry_path}.target",
                    required=True,
                ),
            )
        )

    return tuple(result)


def _parse_vocabularies(
    parser: _SchemaParser,
    root: Mapping[str, Any],
) -> tuple[VocabularyProfile, ...]:
    result: list[VocabularyProfile] = []

    for index, entry in parser.table_array(
        root,
        "vocabularies",
        "vocabularies",
        required=True,
    ):
        path = f"vocabularies[{index}]"

        parser.check_keys(
            entry,
            path,
            {
                "key",
                "role",
                "namespace_iris",
                "prefixes",
                "ontology_iri",
                "version_iri",
                "validation_dependency",
                "catalog_mappings",
                "permitted_products",
                "prohibited_products",
            },
        )

        result.append(
            VocabularyProfile(
                vocabulary_key=parser.string(
                    entry,
                    "key",
                    f"{path}.key",
                    required=True,
                ),
                role=parser.string(
                    entry,
                    "role",
                    f"{path}.role",
                    required=True,
                ),
                namespace_iris=parser.string_tuple(
                    entry,
                    "namespace_iris",
                    f"{path}.namespace_iris",
                ),
                prefixes=_parse_prefixes(
                    parser,
                    entry,
                    path,
                ),
                ontology_iri=parser.optional_string(
                    entry,
                    "ontology_iri",
                    f"{path}.ontology_iri",
                ),
                version_iri=parser.optional_string(
                    entry,
                    "version_iri",
                    f"{path}.version_iri",
                ),
                validation_dependency=parser.boolean(
                    entry,
                    "validation_dependency",
                    f"{path}.validation_dependency",
                ),
                catalog_mappings=_parse_catalog_mappings(
                    parser,
                    entry,
                    path,
                ),
                permitted_products=parser.string_tuple(
                    entry,
                    "permitted_products",
                    f"{path}.permitted_products",
                ),
                prohibited_products=parser.string_tuple(
                    entry,
                    "prohibited_products",
                    f"{path}.prohibited_products",
                ),
            )
        )

    return tuple(result)


def _parse_products(
    parser: _SchemaParser,
    root: Mapping[str, Any],
) -> tuple[ProductDefinition, ...]:
    result: list[ProductDefinition] = []

    for index, entry in parser.table_array(
        root,
        "products",
        "products",
        required=True,
    ):
        path = f"products[{index}]"

        parser.check_keys(
            entry,
            path,
            {
                "key",
                "output_path",
                "type",
                "stable_ontology_iri",
                "release_iri_pattern",
                "imports",
                "dependencies",
                "inclusion_policy",
                "permitted_vocabularies",
                "prohibited_vocabularies",
                "serialization_profile",
                "validation_profile",
                "package_role",
            },
        )

        result.append(
            ProductDefinition(
                product_key=parser.string(
                    entry,
                    "key",
                    f"{path}.key",
                    required=True,
                ),
                output_path=parser.string(
                    entry,
                    "output_path",
                    f"{path}.output_path",
                    required=True,
                ),
                product_type=parser.string(
                    entry,
                    "type",
                    f"{path}.type",
                    required=True,
                ),
                stable_ontology_iri=parser.optional_string(
                    entry,
                    "stable_ontology_iri",
                    f"{path}.stable_ontology_iri",
                ),
                release_iri_pattern=parser.optional_string(
                    entry,
                    "release_iri_pattern",
                    f"{path}.release_iri_pattern",
                ),
                imports=parser.string_tuple(
                    entry,
                    "imports",
                    f"{path}.imports",
                ),
                product_dependencies=parser.string_tuple(
                    entry,
                    "dependencies",
                    f"{path}.dependencies",
                ),
                inclusion_policy=parser.optional_string(
                    entry,
                    "inclusion_policy",
                    f"{path}.inclusion_policy",
                ),
                permitted_vocabularies=parser.string_tuple(
                    entry,
                    "permitted_vocabularies",
                    f"{path}.permitted_vocabularies",
                ),
                prohibited_vocabularies=parser.string_tuple(
                    entry,
                    "prohibited_vocabularies",
                    f"{path}.prohibited_vocabularies",
                ),
                serialization_profile=parser.optional_string(
                    entry,
                    "serialization_profile",
                    f"{path}.serialization_profile",
                ),
                validation_profile=parser.optional_string(
                    entry,
                    "validation_profile",
                    f"{path}.validation_profile",
                ),
                package_role=parser.optional_string(
                    entry,
                    "package_role",
                    f"{path}.package_role",
                ),
            )
        )

    return tuple(result)


def _parse_fixed_count_policies(
    parser: _SchemaParser,
    profile: Mapping[str, Any],
    path: str,
) -> tuple[FixedCountPolicy, ...]:
    result: list[FixedCountPolicy] = []

    for index, entry in parser.table_array(
        profile,
        "fixed_count_policies",
        f"{path}.fixed_count_policies",
    ):
        entry_path = (
            f"{path}.fixed_count_policies[{index}]"
        )

        parser.check_keys(
            entry,
            entry_path,
            {
                "key",
                "expected",
            },
        )

        result.append(
            FixedCountPolicy(
                key=parser.string(
                    entry,
                    "key",
                    f"{entry_path}.key",
                    required=True,
                ),
                expected=parser.integer(
                    entry,
                    "expected",
                    f"{entry_path}.expected",
                    required=True,
                ),
            )
        )

    return tuple(result)


def _parse_validation_profiles(
    parser: _SchemaParser,
    root: Mapping[str, Any],
) -> tuple[ValidationProfile, ...]:
    result: list[ValidationProfile] = []

    for index, entry in parser.table_array(
        root,
        "validation_profiles",
        "validation_profiles",
    ):
        path = f"validation_profiles[{index}]"

        parser.check_keys(
            entry,
            path,
            {
                "key",
                "rdf_parser_checks",
                "owlapi_parser_checks",
                "structural_axiom_roundtrip_checks",
                "annotation_preservation_checks",
                "exact_product_list",
                "import_policy_validation",
                "catalog_validation",
                "allowed_mutable_imports",
                "reasoners",
                "expected_consistency",
                "permitted_unsatisfiable_classes",
                "positive_entailment_tests",
                "negative_entailment_tests",
                "instance_data_tests",
                "swrl_validation",
                "fixed_count_policies",
                "project_specific_validation_commands",
            },
        )

        result.append(
            ValidationProfile(
                profile_key=parser.string(
                    entry,
                    "key",
                    f"{path}.key",
                    required=True,
                ),
                rdf_parser_checks=parser.boolean(
                    entry,
                    "rdf_parser_checks",
                    f"{path}.rdf_parser_checks",
                ),
                owlapi_parser_checks=parser.boolean(
                    entry,
                    "owlapi_parser_checks",
                    f"{path}.owlapi_parser_checks",
                ),
                structural_axiom_roundtrip_checks=parser.boolean(
                    entry,
                    "structural_axiom_roundtrip_checks",
                    f"{path}.structural_axiom_roundtrip_checks",
                ),
                annotation_preservation_checks=parser.boolean(
                    entry,
                    "annotation_preservation_checks",
                    f"{path}.annotation_preservation_checks",
                ),
                exact_product_list=parser.string_tuple(
                    entry,
                    "exact_product_list",
                    f"{path}.exact_product_list",
                ),
                import_policy_validation=parser.boolean(
                    entry,
                    "import_policy_validation",
                    f"{path}.import_policy_validation",
                ),
                catalog_validation=parser.boolean(
                    entry,
                    "catalog_validation",
                    f"{path}.catalog_validation",
                ),
                allowed_mutable_imports=parser.string_tuple(
                    entry,
                    "allowed_mutable_imports",
                    f"{path}.allowed_mutable_imports",
                ),
                reasoners=parser.string_tuple(
                    entry,
                    "reasoners",
                    f"{path}.reasoners",
                ),
                expected_consistency=parser.optional_boolean(
                    entry,
                    "expected_consistency",
                    f"{path}.expected_consistency",
                ),
                permitted_unsatisfiable_classes=parser.string_tuple(
                    entry,
                    "permitted_unsatisfiable_classes",
                    f"{path}.permitted_unsatisfiable_classes",
                ),
                positive_entailment_tests=parser.string_tuple(
                    entry,
                    "positive_entailment_tests",
                    f"{path}.positive_entailment_tests",
                ),
                negative_entailment_tests=parser.string_tuple(
                    entry,
                    "negative_entailment_tests",
                    f"{path}.negative_entailment_tests",
                ),
                instance_data_tests=parser.string_tuple(
                    entry,
                    "instance_data_tests",
                    f"{path}.instance_data_tests",
                ),
                swrl_validation=parser.boolean(
                    entry,
                    "swrl_validation",
                    f"{path}.swrl_validation",
                ),
                fixed_count_policies=_parse_fixed_count_policies(
                    parser,
                    entry,
                    path,
                ),
                project_specific_validation_commands=parser.string_tuple(
                    entry,
                    "project_specific_validation_commands",
                    f"{path}.project_specific_validation_commands",
                ),
            )
        )

    return tuple(result)


def _parse_product_texts(
    parser: _SchemaParser,
    publication: Mapping[str, Any],
    key: str,
) -> tuple[ProductText, ...]:
    result: list[ProductText] = []
    path = f"publication.{key}"

    for index, entry in parser.table_array(
        publication,
        key,
        path,
    ):
        entry_path = f"{path}[{index}]"

        parser.check_keys(
            entry,
            entry_path,
            {
                "product_key",
                "text",
            },
        )

        result.append(
            ProductText(
                product_key=parser.string(
                    entry,
                    "product_key",
                    f"{entry_path}.product_key",
                    required=True,
                ),
                text=parser.string(
                    entry,
                    "text",
                    f"{entry_path}.text",
                    required=True,
                ),
            )
        )

    return tuple(result)


def parse_project_config(
    data: Mapping[str, Any],
) -> ProjectConfig:
    """Parse a schema-v1 mapping into an immutable ``ProjectConfig``.

    This function does not access the filesystem and does not perform
    cross-reference or project-policy validation.
    """

    if not isinstance(data, Mapping):
        raise ConfigSchemaError(
            (
                ConfigSchemaIssue(
                    code="invalid_type",
                    path="<root>",
                    message="expected configuration table",
                ),
            )
        )

    parser = _SchemaParser()

    parser.check_keys(
        data,
        "",
        {
            "schema_version",
            "project",
            "workbook",
            "vocabularies",
            "expressions",
            "products",
            "validation_profiles",
            "publication",
            "release",
        },
    )

    schema_version = parser.string(
        data,
        "schema_version",
        "schema_version",
        required=True,
    )

    if (
        schema_version
        and schema_version
        != SUPPORTED_CONFIGURATION_SCHEMA_VERSION
    ):
        parser.issue(
            "unsupported_schema_version",
            "schema_version",
            (
                "unsupported configuration schema version: "
                f"{schema_version}"
            ),
        )

    project = parser.table(
        data,
        "project",
        "project",
        required=True,
    )

    parser.check_keys(
        project,
        "project",
        {
            "key",
            "title",
            "repository_root",
            "authoritative_mapping_source",
            "primary_output",
            "generated_warning",
        },
    )

    project_key = parser.string(
        project,
        "key",
        "project.key",
        required=True,
    )

    project_title = parser.string(
        project,
        "title",
        "project.title",
        required=True,
    )

    repository_root = parser.string(
        project,
        "repository_root",
        "project.repository_root",
        required=True,
    )

    authoritative_mapping_source = parser.string(
        project,
        "authoritative_mapping_source",
        "project.authoritative_mapping_source",
        required=True,
    )

    primary_output = parser.string(
        project,
        "primary_output",
        "project.primary_output",
        required=True,
    )

    generated_warning = parser.string(
        project,
        "generated_warning",
        "project.generated_warning",
        required=True,
    )

    workbook = parser.table(
        data,
        "workbook",
        "workbook",
        required=True,
    )

    parser.check_keys(
        workbook,
        "workbook",
        {
            "path",
            "sheet_selectors",
            "header_bindings",
            "required_columns",
            "optional_columns",
            "documentation_only_columns",
            "row_id_column",
            "allowed_expression_types",
            "explicit_blank_representation",
        },
    )

    workbook_profile = WorkbookProfile(
        workbook_path=parser.string(
            workbook,
            "path",
            "workbook.path",
            required=True,
        ),
        sheet_selectors=parser.string_tuple(
            workbook,
            "sheet_selectors",
            "workbook.sheet_selectors",
        ),
        header_bindings=_parse_header_bindings(
            parser,
            workbook,
        ),
        required_columns=parser.string_tuple(
            workbook,
            "required_columns",
            "workbook.required_columns",
        ),
        optional_columns=parser.string_tuple(
            workbook,
            "optional_columns",
            "workbook.optional_columns",
        ),
        documentation_only_columns=parser.string_tuple(
            workbook,
            "documentation_only_columns",
            "workbook.documentation_only_columns",
        ),
        row_id_column=parser.string(
            workbook,
            "row_id_column",
            "workbook.row_id_column",
            required=True,
        ),
        allowed_expression_types=parser.string_tuple(
            workbook,
            "allowed_expression_types",
            "workbook.allowed_expression_types",
        ),
        explicit_blank_representation=parser.optional_string(
            workbook,
            "explicit_blank_representation",
            "workbook.explicit_blank_representation",
        ),
    )

    expressions = parser.table(
        data,
        "expressions",
        "expressions",
        required=True,
    )

    parser.check_keys(
        expressions,
        "expressions",
        {
            "allowed_owl_predicates",
            "allowed_skos_predicates",
            "swrl_enabled",
            "supported_complex_expression_grammar",
            "annotation_policies",
            "transformation_registry",
            "canonicalization_version",
        },
    )

    expression_profile = ExpressionProfile(
        allowed_owl_predicates=parser.string_tuple(
            expressions,
            "allowed_owl_predicates",
            "expressions.allowed_owl_predicates",
        ),
        allowed_skos_predicates=parser.string_tuple(
            expressions,
            "allowed_skos_predicates",
            "expressions.allowed_skos_predicates",
        ),
        swrl_enabled=parser.boolean(
            expressions,
            "swrl_enabled",
            "expressions.swrl_enabled",
        ),
        supported_complex_expression_grammar=parser.string_tuple(
            expressions,
            "supported_complex_expression_grammar",
            "expressions.supported_complex_expression_grammar",
        ),
        annotation_policies=parser.string_tuple(
            expressions,
            "annotation_policies",
            "expressions.annotation_policies",
        ),
        transformation_registry=parser.string_tuple(
            expressions,
            "transformation_registry",
            "expressions.transformation_registry",
        ),
        canonicalization_version=parser.string(
            expressions,
            "canonicalization_version",
            "expressions.canonicalization_version",
        ),
    )

    publication = parser.table(
        data,
        "publication",
        "publication",
        required=True,
    )

    parser.check_keys(
        publication,
        "publication",
        {
            "project_title",
            "stable_ontology_iris",
            "version_iri_policy",
            "release_identifier_format",
            "repository_iri",
            "license_iri",
            "creators",
            "contributors",
            "development_status",
            "product_labels",
            "product_descriptions",
        },
    )

    publication_title = parser.optional_string(
        publication,
        "project_title",
        "publication.project_title",
    )

    publication_profile = PublicationProfile(
        project_title=(
            publication_title
            if publication_title is not None
            else project_title
        ),
        stable_ontology_iris=parser.string_tuple(
            publication,
            "stable_ontology_iris",
            "publication.stable_ontology_iris",
        ),
        version_iri_policy=parser.optional_string(
            publication,
            "version_iri_policy",
            "publication.version_iri_policy",
        ),
        release_identifier_format=parser.optional_string(
            publication,
            "release_identifier_format",
            "publication.release_identifier_format",
        ),
        repository_iri=parser.optional_string(
            publication,
            "repository_iri",
            "publication.repository_iri",
        ),
        license_iri=parser.optional_string(
            publication,
            "license_iri",
            "publication.license_iri",
        ),
        creators=parser.string_tuple(
            publication,
            "creators",
            "publication.creators",
        ),
        contributors=parser.string_tuple(
            publication,
            "contributors",
            "publication.contributors",
        ),
        development_status=parser.optional_string(
            publication,
            "development_status",
            "publication.development_status",
        ),
        product_labels=_parse_product_texts(
            parser,
            publication,
            "product_labels",
        ),
        product_descriptions=_parse_product_texts(
            parser,
            publication,
            "product_descriptions",
        ),
    )

    release = parser.table(
        data,
        "release",
        "release",
        required=True,
    )

    parser.check_keys(
        release,
        "release",
        {
            "archive_prefix",
            "package_members",
            "source_artifacts",
            "evidence_artifacts",
            "product_artifacts",
            "manifest_path",
            "checksum_path",
            "release_notes_path",
            "required_release_note_sections",
        },
    )

    release_layout = ReleaseLayout(
        archive_prefix=parser.string(
            release,
            "archive_prefix",
            "release.archive_prefix",
            required=True,
        ),
        package_members=parser.string_tuple(
            release,
            "package_members",
            "release.package_members",
        ),
        source_artifacts=parser.string_tuple(
            release,
            "source_artifacts",
            "release.source_artifacts",
        ),
        evidence_artifacts=parser.string_tuple(
            release,
            "evidence_artifacts",
            "release.evidence_artifacts",
        ),
        product_artifacts=parser.string_tuple(
            release,
            "product_artifacts",
            "release.product_artifacts",
        ),
        manifest_path=parser.optional_string(
            release,
            "manifest_path",
            "release.manifest_path",
        ),
        checksum_path=parser.optional_string(
            release,
            "checksum_path",
            "release.checksum_path",
        ),
        release_notes_path=parser.optional_string(
            release,
            "release_notes_path",
            "release.release_notes_path",
        ),
        required_release_note_sections=parser.string_tuple(
            release,
            "required_release_note_sections",
            "release.required_release_note_sections",
        ),
    )

    vocabularies = _parse_vocabularies(
        parser,
        data,
    )

    products = _parse_products(
        parser,
        data,
    )

    validation_profiles = _parse_validation_profiles(
        parser,
        data,
    )

    if parser.issues:
        raise ConfigSchemaError(
            parser.issues
        )

    return ProjectConfig(
        project_key=project_key,
        project_title=project_title,
        repository_root=repository_root,
        authoritative_mapping_source=authoritative_mapping_source,
        primary_output=primary_output,
        generated_warning=generated_warning,
        configuration_schema_version=schema_version,
        workbook=workbook_profile,
        vocabularies=vocabularies,
        expressions=expression_profile,
        product_graph=ProductGraph(
            products=products,
        ),
        validation_profiles=validation_profiles,
        publication=publication_profile,
        release_layout=release_layout,
    )
