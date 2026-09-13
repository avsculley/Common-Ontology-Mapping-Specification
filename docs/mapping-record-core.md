# Governed mapping record core

`coms.mapping_record.GovernedMappingRecord` is the project-neutral semantic
record between source-format parsing and canonical identity / ontology
compilation.

The intended pipeline is:

```text
source row or other input
        |
        v
source-format parser / resolver
        |
        v
GovernedMappingRecord
        |
        +----> row identity / canonical axiom identity
        |
        +----> future ontology compiler
```

## Record semantics

A governed mapping record contains:

- `row_id` — the stable governed COMS row identifier;
- `subject_iri` — the resolved source entity IRI;
- `predicate_iri` — the resolved mapping or OWL/RDFS predicate IRI, or `None`
  for an explicit blank mapping;
- `mapping_type` — the normalized semantic mapping category used by COMS;
- `reasoning` — human governance rationale carried with the record;
- `expression` — an optional resolved class expression;
- `target_property_iri` — an optional resolved property target;
- `property_chain` — an optional ordered tuple of resolved property IRIs.

An active mapping uses one semantic target representation. An explicit blank
mapping uses none. Structural enforcement remains in the established
row-identity machinery during this compatibility-preserving extraction.

## What is deliberately absent

The governed record does not contain:

- workbook path;
- worksheet name;
- physical row number;
- raw subject, predicate, or target cell text;
- Excel or OpenPyXL objects;
- RDFLib nodes;
- label-resolution records;
- generated ontology objects;
- identity-audit results;
- project-specific ontology names.

Those belong either to the source adapter, validation context, or downstream
compiler.

## Location and identity

Physical source location is diagnostic provenance, not part of semantic mapping
identity. `RowLocation` therefore remains external to
`GovernedMappingRecord`.

`row_identity.canonical_input_for_mapping_record(record, location)` supplies
that diagnostic location when the record enters RowID/axiom auditing.

The stable RowID and the human reasoning note are carried by the governed
record, but neither changes the canonical source-expression hash. The
canonical semantic identity continues to depend on mapping type, predicate,
subject, and canonical target.

## Compatibility

`CanonicalRowInput` remains available in `coms.row_identity`. Existing users
therefore retain the current API while new source adapters can target
`GovernedMappingRecord`.

This increment does not define workbook parsing or RDF/OWL compilation.
