# COMS Configuration Schema v1

## Purpose

COMS project configuration is an external, project-neutral contract.

Schema v1 is designed for TOML, but the core parser consumes an already
decoded mapping. File I/O is intentionally separate from schema parsing.

The external schema does not mechanically reproduce the Python dataclass
layout. In particular:

- `[[products]]` is assembled into the internal `ProductGraph`;
- product `dependencies` become internal `product_dependencies`;
- product `type` becomes internal `product_type`;
- vocabulary `key` becomes internal `vocabulary_key`;
- validation-profile `key` becomes internal `profile_key`;
- `publication.project_title` may be omitted and then defaults to
  `project.title`.

Schema parsing validates structure and primitive types. Cross-reference,
constraint, graph, and other project semantics are validated separately by
`validate_project_config`.

## Top-level structure

The supported schema identifier is:

```toml
schema_version = "1"
```

Schema v1 permits these top-level entries:

```text
schema_version
project
workbook
vocabularies
expressions
products
validation_profiles
publication
release
```

Unknown keys are schema errors.

`validation_profiles` and `release` may be omitted. The other major sections
are required.

## Project

```toml
[project]
key = "example-mapping"
title = "Example Mapping Project"
repository_root = "."
authoritative_mapping_source = "workbook"
primary_output = "integrated"
generated_warning = "GENERATED FILE"
```

All six fields are required strings.

`primary_output` is intentionally treated as an opaque project configuration
value in schema v1. The generic schema does not yet define it as a product key,
path, or other reference.

## Workbook

```toml
[workbook]
path = "mappings/example.xlsx"
sheet_selectors = ["Classes", "Properties"]
required_columns = ["RowID", "Source", "Target"]
optional_columns = ["Comment"]
documentation_only_columns = ["Comment"]
row_id_column = "RowID"
allowed_expression_types = ["class_mapping"]
explicit_blank_representation = ""

[[workbook.header_bindings]]
field = "row_id"
column = "RowID"

[[workbook.header_bindings]]
field = "source"
column = "Source"

[[workbook.header_bindings]]
field = "target"
column = "Target"
```

Required fields:

- `path`
- `row_id_column`

All other workbook fields are optional.

## Vocabularies

Each vocabulary is declared independently:

```toml
[[vocabularies]]
key = "source"
role = "source"
namespace_iris = ["https://example.org/source/"]
ontology_iri = "https://example.org/source"
validation_dependency = false
permitted_products = ["alignment", "integrated"]

[[vocabularies.prefixes]]
prefix = "src"
namespace_iri = "https://example.org/source/"

[[vocabularies.catalog_mappings]]
ontology_iri = "https://example.org/source"
target = "imports/source.ttl"
```

Required vocabulary fields:

- `key`
- `role`

Supported semantic role values are enforced by configuration validation rather
than by schema parsing.

Optional vocabulary fields:

- `namespace_iris`
- `prefixes`
- `ontology_iri`
- `version_iri`
- `validation_dependency`
- `catalog_mappings`
- `permitted_products`
- `prohibited_products`

## Expressions

```toml
[expressions]
allowed_owl_predicates = [
  "http://www.w3.org/2000/01/rdf-schema#subClassOf",
]
allowed_skos_predicates = []
swrl_enabled = false
supported_complex_expression_grammar = []
annotation_policies = []
transformation_registry = []
canonicalization_version = "example-v1"
```

Every field in this section is optional.

## Products

Products are declared as a flat external collection. COMS constructs the
internal product graph from their keys and dependency declarations.

```toml
[[products]]
key = "alignment"
output_path = "build/alignment.ttl"
type = "mapping"
stable_ontology_iri = "https://example.org/alignment"
permitted_vocabularies = ["source"]
validation_profile = "default"

[[products]]
key = "integrated"
output_path = "build/integrated.ttl"
type = "integrated"
dependencies = ["alignment"]
permitted_vocabularies = ["source", "target"]
validation_profile = "default"
```

Required product fields:

- `key`
- `output_path`
- `type`

Optional fields:

- `stable_ontology_iri`
- `release_iri_pattern`
- `imports`
- `dependencies`
- `inclusion_policy`
- `permitted_vocabularies`
- `prohibited_vocabularies`
- `serialization_profile`
- `validation_profile`
- `package_role`

`imports` and `dependencies` are intentionally distinct. The former expresses
ontology-import configuration; the latter defines the COMS product dependency
graph.

## Validation profiles

```toml
[[validation_profiles]]
key = "default"
rdf_parser_checks = true
owlapi_parser_checks = true
exact_product_list = ["alignment", "integrated"]
expected_consistency = true
instance_data_tests = ["tests/fixtures/instances.ttl"]

[[validation_profiles.fixed_count_policies]]
key = "mapping-count"
expected = 5
```

Only `key` is required.

Optional fields correspond to the project-neutral validation capabilities:

- `rdf_parser_checks`
- `owlapi_parser_checks`
- `structural_axiom_roundtrip_checks`
- `annotation_preservation_checks`
- `exact_product_list`
- `import_policy_validation`
- `catalog_validation`
- `allowed_mutable_imports`
- `reasoners`
- `expected_consistency`
- `permitted_unsatisfiable_classes`
- `positive_entailment_tests`
- `negative_entailment_tests`
- `instance_data_tests`
- `swrl_validation`
- `fixed_count_policies`
- `project_specific_validation_commands`

## Publication

```toml
[publication]
repository_iri = "https://example.org/repository"
license_iri = "https://example.org/license"
creators = ["Example Creator"]
contributors = []
development_status = "development"

[[publication.product_labels]]
product_key = "integrated"
text = "Integrated Mapping"

[[publication.product_descriptions]]
product_key = "integrated"
text = "Integrated mapping product for the synthetic example."
```

`publication.project_title` is optional. If omitted, it defaults to
`project.title`.

Other optional publication fields are:

- `stable_ontology_iris`
- `version_iri_policy`
- `release_identifier_format`
- `repository_iri`
- `license_iri`
- `creators`
- `contributors`
- `development_status`
- `product_labels`
- `product_descriptions`

## Release

```toml
[release]
archive_prefix = "example-release"
package_members = []
source_artifacts = []
evidence_artifacts = []
product_artifacts = ["build/integrated.ttl"]
manifest_path = "release/manifest.json"
checksum_path = "release/SHA256SUMS"
release_notes_path = "release/README.md"
required_release_note_sections = ["Products", "Validation"]
```

The entire `release` section may be omitted when a mapping project does not
define formal release or package behavior.

All release-layout fields, including `archive_prefix`, are optional in schema
v1. A later framework operation that actually constructs or validates a
release package is responsible for requiring the release configuration needed
for that operation.

## Validation boundary

Schema parsing does **not**:

- resolve paths;
- require files or directories to exist;
- inspect ontology documents;
- validate product dependency cycles;
- validate vocabulary/product references;
- reconcile permit/prohibit constraints;
- invoke parsers, reasoners, or project commands.

Those responsibilities belong to configuration semantic validation or later
runtime framework layers.

## Loading TOML

The public `load_project_config(path)` function is the filesystem-facing
adapter for schema v1. It:

1. opens the specified file in binary mode;
2. decodes TOML using Python's standard-library `tomllib`;
3. passes the decoded mapping to `parse_project_config`.

Loading is deliberately separate from both schema parsing and semantic
validation.

`ConfigLoadError` reports file-read, TOML-syntax, or UTF-8 decoding failures.
`ConfigSchemaError` continues to report external schema violations.

A successful load does not imply that the configuration is semantically
valid. Call `validate_project_config` separately to check cross-references,
product dependency cycles, permit/prohibit constraints, and related project
semantics.

The loader does not:

- resolve configured paths relative to the configuration file;
- require referenced files or directories to exist;
- inspect workbooks or ontologies;
- invoke `validate_project_config`;
- invoke parsers, reasoners, release tooling, or project commands.
