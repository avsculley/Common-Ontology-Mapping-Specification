"""Orchestrate selected workbook rows through existing COMS authorities."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .adapters.xlsx import WorkbookSourceRow
from .mapping_parser import EntityResolver
from .mapping_record import GovernedMappingRecord
from .row_identity import (
    CanonicalRowAudit,
    ComsRowIdentityError,
    RowIdentityReference,
    ValidationIssue,
    build_row_audit,
    canonical_input_for_mapping_record,
    validate_row_id,
    validate_unique_authoritative_axioms,
    validate_unique_row_ids,
)
from .workbook_mapping import (
    SourceEntityResolver,
    build_governed_mapping_record_from_workbook_row,
)


@dataclass(frozen=True)
class AuditedWorkbookRow:
    """Associate one lexical source row with its semantics and identity audit."""

    source_row: WorkbookSourceRow
    governed_record: GovernedMappingRecord
    row_audit: CanonicalRowAudit


def _validate_materialized_row_ids(
    rows: tuple[WorkbookSourceRow, ...],
) -> None:
    references: list[RowIdentityReference] = []
    issues: list[ValidationIssue] = []

    for row in rows:
        try:
            row_id = validate_row_id(
                row.row_id_text,
                row.location,
            )
        except ComsRowIdentityError as exc:
            issues.extend(
                exc.issues
            )
            continue

        references.append(
            RowIdentityReference(
                row_id=row_id,
                location=row.location,
            )
        )

    issues.extend(
        validate_unique_row_ids(
            references
        )
    )

    if issues:
        raise ComsRowIdentityError(
            issues
        )


def validate_workbook_source_row_ids(
    rows: Iterable[WorkbookSourceRow],
) -> None:
    """Validate RowIDs across a complete governed source-row collection."""

    source_rows = tuple(
        rows
    )
    _validate_materialized_row_ids(
        source_rows
    )


def _row_diagnostic_note(
    row: WorkbookSourceRow,
) -> str:
    return (
        "Workbook source row: "
        f"{row.location.text} "
        f"[{row.row_id_text}]"
    )


def _add_row_diagnostic_note(
    error: Exception,
    row: WorkbookSourceRow,
) -> None:
    note = _row_diagnostic_note(
        row
    )

    if note not in getattr(
        error,
        "__notes__",
        (),
    ):
        error.add_note(
            note
        )


def build_governed_workbook_batch(
    rows: Iterable[WorkbookSourceRow],
    source_resolver: SourceEntityResolver,
    target_resolver: EntityResolver,
) -> tuple[AuditedWorkbookRow, ...]:
    """Build and audit an already-selected workbook row collection."""

    source_rows = tuple(
        rows
    )
    _validate_materialized_row_ids(
        source_rows
    )

    audited_rows: list[
        AuditedWorkbookRow
    ] = []

    for source_row in source_rows:
        try:
            governed_record = (
                build_governed_mapping_record_from_workbook_row(
                    source_row,
                    source_resolver,
                    target_resolver,
                )
            )
            row_audit = build_row_audit(
                canonical_input_for_mapping_record(
                    governed_record,
                    source_row.location,
                )
            )
        except Exception as exc:
            _add_row_diagnostic_note(
                exc,
                source_row,
            )
            raise

        audited_rows.append(
            AuditedWorkbookRow(
                source_row=source_row,
                governed_record=governed_record,
                row_audit=row_audit,
            )
        )

    duplicate_issues = (
        validate_unique_authoritative_axioms(
            item.row_audit
            for item in audited_rows
        )
    )

    if duplicate_issues:
        raise ComsRowIdentityError(
            duplicate_issues
        )

    return tuple(
        audited_rows
    )
