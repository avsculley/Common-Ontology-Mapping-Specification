"""Read configured XLSX workbooks into unresolved COMS source rows."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Any

from ..config import WorkbookProfile
from ..row_identity import RowLocation


_DEFAULT_HEADERS = {
    "row_id": "coms:RowID",
    "source": "sssom:subject_id",
    "predicate": "sssom:predicate_id",
    "target": "coms:Target",
    "reasoning": "coms:Reasoning",
    "status": "coms:MappingStatus",
}

_SUPPORTED_BINDING_FIELDS = frozenset(
    _DEFAULT_HEADERS
)

_REQUIRED_FIELDS = (
    "source",
    "predicate",
    "target",
    "reasoning",
)


class XlsxAdapterError(ValueError):
    """An XLSX workbook does not satisfy its extraction contract."""


class XlsxAdapterDependencyError(ImportError):
    """The optional XLSX adapter dependency is unavailable."""


@dataclass(frozen=True)
class WorkbookSourceRow:
    """One unresolved lexical workbook row with physical provenance."""

    location: RowLocation
    row_id_text: str
    subject_text: str
    predicate_text: str
    target_text: str
    reasoning_text: str
    status_text: str | None


def _normalize_cell(value: object) -> str:
    if value is None:
        return ""

    return str(value).strip()


def _openpyxl() -> Any:
    try:
        return import_module("openpyxl")
    except ModuleNotFoundError as exc:
        raise XlsxAdapterDependencyError(
            "OpenPyXL is required for XLSX workbook extraction; "
            "install the project with the 'xlsx' extra"
        ) from exc


def _duplicate_values(
    values: tuple[str, ...],
) -> tuple[str, ...]:
    counts = Counter(values)
    return tuple(
        sorted(
            value
            for value, count in counts.items()
            if value and count > 1
        )
    )


def _header_contract(
    profile: WorkbookProfile,
) -> dict[str, str]:
    if not profile.row_id_column:
        raise XlsxAdapterError(
            "workbook profile requires a nonblank row_id_column"
        )

    duplicate_fields = _duplicate_values(
        tuple(
            binding.field
            for binding in profile.header_bindings
        )
    )

    if duplicate_fields:
        raise XlsxAdapterError(
            "ambiguous workbook header bindings for fields: "
            + ", ".join(duplicate_fields)
        )

    duplicate_columns = _duplicate_values(
        tuple(
            binding.column
            for binding in profile.header_bindings
        )
    )

    if duplicate_columns:
        raise XlsxAdapterError(
            "ambiguous workbook header bindings for columns: "
            + ", ".join(duplicate_columns)
        )

    unsupported_fields = tuple(
        sorted(
            binding.field
            for binding in profile.header_bindings
            if binding.field not in _SUPPORTED_BINDING_FIELDS
        )
    )

    if unsupported_fields:
        raise XlsxAdapterError(
            "unsupported workbook header binding fields: "
            + ", ".join(unsupported_fields)
        )

    headers = dict(_DEFAULT_HEADERS)
    headers["row_id"] = profile.row_id_column

    for binding in profile.header_bindings:
        if not binding.column:
            raise XlsxAdapterError(
                "workbook header binding columns must be nonblank"
            )

        if (
            binding.field == "row_id"
            and binding.column != profile.row_id_column
        ):
            raise XlsxAdapterError(
                "row_id header binding must match row_id_column"
            )

        headers[binding.field] = binding.column

    duplicate_governed_columns = _duplicate_values(
        tuple(headers.values())
    )

    if duplicate_governed_columns:
        raise XlsxAdapterError(
            "multiple governed fields use the same workbook column: "
            + ", ".join(duplicate_governed_columns)
        )

    return headers


def _worksheet_headers(
    worksheet: Any,
) -> tuple[tuple[Any, ...], tuple[str, ...]]:
    cells = tuple(
        next(
            worksheet.iter_rows(
                min_row=1,
                max_row=1,
            )
        )
    )
    return cells, tuple(
        _normalize_cell(cell.value)
        for cell in cells
    )


def _validate_headers(
    *,
    worksheet: Any,
    header_cells: tuple[Any, ...],
    header_values: tuple[str, ...],
    field_headers: dict[str, str],
    profile: WorkbookProfile,
) -> dict[str, int]:
    configured_headers = frozenset(
        (
            *field_headers.values(),
            *profile.required_columns,
            *profile.optional_columns,
            *profile.documentation_only_columns,
        )
    )

    counts = Counter(header_values)
    duplicates = tuple(
        sorted(
            header
            for header, count in counts.items()
            if (
                header
                and count > 1
                and header in configured_headers
            )
        )
    )

    if duplicates:
        raise XlsxAdapterError(
            f"{worksheet.title}!1: duplicate governed/configured "
            "headers: "
            + ", ".join(duplicates)
        )

    header_index = {
        header: index
        for index, header in enumerate(header_values)
        if header
    }

    row_id_header = field_headers["row_id"]

    if row_id_header not in header_index:
        raise XlsxAdapterError(
            f"{worksheet.title}!1: missing configured RowID header "
            f"{row_id_header!r}"
        )

    required_headers = tuple(
        dict.fromkeys(
            (
                *(field_headers[field] for field in _REQUIRED_FIELDS),
                *profile.required_columns,
            )
        )
    )
    missing = tuple(
        header
        for header in required_headers
        if header not in header_index
    )

    if missing:
        raise XlsxAdapterError(
            f"{worksheet.title}!1: missing required headers: "
            + ", ".join(missing)
        )

    governed_indexes = {
        field: header_index[header]
        for field, header in field_headers.items()
        if header in header_index
    }

    for field, index in governed_indexes.items():
        if header_cells[index].data_type == "f":
            raise XlsxAdapterError(
                f"{worksheet.title}!1: formula is not allowed in "
                f"governed header field {field!r}"
            )

    return governed_indexes


def _extract_worksheet_rows(
    *,
    worksheet: Any,
    header_cells: tuple[Any, ...],
    header_values: tuple[str, ...],
    field_headers: dict[str, str],
    profile: WorkbookProfile,
) -> tuple[WorkbookSourceRow, ...]:
    indexes = _validate_headers(
        worksheet=worksheet,
        header_cells=header_cells,
        header_values=header_values,
        field_headers=field_headers,
        profile=profile,
    )
    rows: list[WorkbookSourceRow] = []

    for row_number, cells in enumerate(
        worksheet.iter_rows(
            min_row=2,
        ),
        start=2,
    ):
        values: dict[str, str] = {}

        for field, index in indexes.items():
            cell = cells[index]

            if cell.data_type == "f":
                raise XlsxAdapterError(
                    f"{worksheet.title}!{cell.coordinate}: formula is "
                    f"not allowed in governed field {field!r}"
                )

            values[field] = _normalize_cell(
                cell.value
            )

        status_text = (
            values["status"]
            if "status" in values
            else None
        )

        governed_values = (
            values["row_id"],
            values["source"],
            values["predicate"],
            values["target"],
            values["reasoning"],
            *(()
              if status_text is None
              else (status_text,)),
        )

        if not any(governed_values):
            continue

        rows.append(
            WorkbookSourceRow(
                location=RowLocation(
                    worksheet=worksheet.title,
                    row_number=row_number,
                ),
                row_id_text=values["row_id"],
                subject_text=values["source"],
                predicate_text=values["predicate"],
                target_text=values["target"],
                reasoning_text=values["reasoning"],
                status_text=status_text,
            )
        )

    return tuple(rows)


def read_xlsx_source_rows(
    profile: WorkbookProfile,
    *,
    base_directory: str | Path = ".",
) -> tuple[WorkbookSourceRow, ...]:
    """Extract unresolved governed rows from one configured XLSX workbook."""

    field_headers = _header_contract(
        profile
    )

    duplicate_selectors = _duplicate_values(
        profile.sheet_selectors
    )

    if duplicate_selectors:
        raise XlsxAdapterError(
            "duplicate workbook sheet selectors: "
            + ", ".join(duplicate_selectors)
        )

    workbook_path = Path(
        profile.workbook_path
    )

    if not workbook_path.is_absolute():
        workbook_path = (
            Path(base_directory)
            / workbook_path
        )

    openpyxl = _openpyxl()
    workbook = openpyxl.load_workbook(
        workbook_path,
        read_only=True,
        data_only=False,
    )

    try:
        headers_by_sheet = {
            worksheet.title: _worksheet_headers(
                worksheet
            )
            for worksheet in workbook.worksheets
        }

        if profile.sheet_selectors:
            missing_selectors = tuple(
                selector
                for selector in profile.sheet_selectors
                if selector not in workbook.sheetnames
            )

            if missing_selectors:
                raise XlsxAdapterError(
                    "missing configured workbook sheets: "
                    + ", ".join(missing_selectors)
                )

            worksheets = tuple(
                workbook[selector]
                for selector in profile.sheet_selectors
            )
        else:
            discovery_headers = {
                field_headers[field]
                for field in (
                    "row_id",
                    *_REQUIRED_FIELDS,
                )
            }
            discovery_headers.update(
                profile.required_columns
            )
            worksheets = tuple(
                worksheet
                for worksheet in workbook.worksheets
                if discovery_headers.issubset(
                    headers_by_sheet[
                        worksheet.title
                    ][1]
                )
            )

            if not worksheets:
                raise XlsxAdapterError(
                    f"no governed worksheets found in {workbook_path}"
                )

        extracted: list[
            WorkbookSourceRow
        ] = []

        for worksheet in worksheets:
            header_cells, header_values = (
                headers_by_sheet[
                    worksheet.title
                ]
            )
            extracted.extend(
                _extract_worksheet_rows(
                    worksheet=worksheet,
                    header_cells=header_cells,
                    header_values=header_values,
                    field_headers=field_headers,
                    profile=profile,
                )
            )

        return tuple(extracted)
    finally:
        workbook.close()
