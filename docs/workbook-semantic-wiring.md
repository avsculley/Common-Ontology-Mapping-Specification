# Workbook semantic wiring

`coms.workbook_mapping` bridges one unresolved workbook row into the existing
mapping-record builder:

```text
WorkbookSourceRow
    ↓
source resolution + predicate normalization
    ↓
existing mapping-record builder
    ↓
GovernedMappingRecord
```

Projects supply `SourceEntityResolver` to resolve a source token and report
whether it denotes a class or object property. Projects also supply the
existing `EntityResolver` for target class expressions and object properties.
The wiring layer does not load ontologies, resolve labels, or restrict project
prefixes.

Predicate normalization recognizes only the seven mapping predicates already
supported by COMS. Each may be written as its conventional `rdfs:` or `owl:`
CURIE or as the corresponding full IRI. Blank predicate text remains `None`
for the existing explicit-blank behavior; arbitrary CURIE expansion is not
performed.

Workflow status does not affect this operation. Projects decide which rows to
submit. RowID text is copied without validation, and physical `RowLocation`
remains on `WorkbookSourceRow` for later use with the row-identity layer. The
wiring operation builds one semantic record at a time and performs no identity
audit, ontology compilation, publication, or file writing.
