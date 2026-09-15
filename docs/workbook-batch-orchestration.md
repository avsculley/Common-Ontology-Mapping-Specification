# Workbook batch orchestration

`coms.workbook_batch` connects complete workbook identity preflight with
semantic processing of an already-selected row collection:

```text
all governed WorkbookSourceRow values
        ↓
validate_workbook_source_row_ids
        ↓
project workflow selection
        ↓
build_governed_workbook_batch
        ↓
ordered AuditedWorkbookRow values
```

## RowID preflight

RowID syntax and uniqueness are workbook governance, so projects call
`validate_workbook_source_row_ids` on the complete governed extraction before
excluding rows through workflow policy. The operation accumulates all RowID
syntax issues and then uses the existing duplicate-RowID authority. It does
not resolve entities or inspect workflow status.

The selected-row batch builder repeats the same preflight on its own input so
it cannot return a validated batch with missing, malformed, or duplicate
RowIDs.

## Selected semantic batch

`build_governed_workbook_batch` receives one reusable source resolver and one
reusable target resolver. It calls the existing one-row workbook wiring and
row-identity operations for each selected row in caller order. Resolver
caching, ontology resources, label indexes, and project policy remain inside
resolver implementations.

Each successful result is a frozen `AuditedWorkbookRow` associating the
original `WorkbookSourceRow`, its `GovernedMappingRecord`, and its existing
`CanonicalRowAudit`. Physical location remains available through the source
row and audit but does not enter the semantic record or mapping identity.

Semantic processing is fail-fast. Existing exception types and messages are
preserved, with a deterministic exception note identifying the source RowID
and physical location. No partial batch is returned.

After every selected row has wired and audited successfully, the batch uses
the existing authoritative-axiom duplicate validator. Duplicate canonical
axioms are fatal and are never silently removed. Explicit blanks naturally
contribute no authoritative axioms.

## Policy boundaries

Workflow status is opaque to the batch layer. Projects decide which rows to
submit. A submitted row with blank predicate and target retains the existing
explicit-blank semantics.

Multiple rows may use the same subject and predicate with different targets;
those rows can represent distinct OWL axioms. Project-specific authoring rules
may prohibit that pattern, but generic COMS does not. Canonically identical
axioms remain duplicate errors.

The batch layer does not consume `allowed_expression_types` or
`explicit_blank_representation`, whose runtime meanings remain deferred. It
does not select product members, compile ontology statements, render ontology
documents, write files, report statistics, load ontology graphs, or run
reasoners. A later project/product layer selects `governed_record` values and
passes them to the existing ontology document composer.
