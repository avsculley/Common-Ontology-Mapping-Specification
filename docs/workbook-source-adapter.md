# XLSX Workbook Source Adapter

## Purpose

The optional XLSX adapter is lexical source-format infrastructure. It reads a
configured COMS workbook without modifying it and emits immutable
`WorkbookSourceRow` values:

```text
XLSX workbook
    ↓
WorkbookSourceRow
    ↓
future source and predicate resolution
    ↓
GovernedMappingRecord
```

Each source row contains normalized unresolved text for RowID, subject,
predicate, target, reasoning, and optional status together with the existing
`RowLocation` physical provenance. `None` cells become empty strings; other
values are converted to strings and stripped of surrounding whitespace.

## Configuration and selection

`WorkbookProfile` remains the workbook configuration authority. The adapter
supports the documented logical binding names `row_id`, `source`, `predicate`,
`target`, `reasoning`, and `status`. The configured `row_id_column` remains the
RowID-header authority and must agree with a `row_id` header binding when both
are supplied.

When `sheet_selectors` is nonempty, sheets are processed in configured order
and missing or duplicate selectors are errors. Otherwise, governed sheets are
discovered in physical workbook order by their bound source, predicate,
target, and reasoning headers. Every selected or discovered sheet must also
contain the configured RowID header and all configured required headers.

Headers are read from row 1. Physical column order is irrelevant. Duplicate
governed/configured headers and ambiguous bindings are rejected. Unconfigured
extra columns are ignored.

Rows retain physical order and row number. A row is skipped only when every
extracted governed field is blank after normalization. Nonempty malformed rows
are deliberately retained for later validation.

## Boundaries

The adapter opens workbooks with OpenPyXL in read-only mode, reads source
formula text rather than cached results, rejects formulas in governed cells,
never saves the workbook, and never exposes the workbook object. XLSX support
is provided by the optional `xlsx` dependency extra.

The adapter does not:

- validate RowID syntax or uniqueness;
- resolve or normalize subjects, predicates, or targets;
- inspect ontology declarations or load RDF graphs;
- interpret mapping status;
- parse mapping expressions or property chains;
- build `GovernedMappingRecord` values;
- compile or publish ontology output.

Those responsibilities remain in the existing downstream semantic and
project-adapter layers.
