"""Optional source-format adapters for COMS."""

from .xlsx import (
    WorkbookSourceRow,
    XlsxAdapterDependencyError,
    XlsxAdapterError,
    read_xlsx_source_rows,
)


__all__ = [
    "WorkbookSourceRow",
    "XlsxAdapterDependencyError",
    "XlsxAdapterError",
    "read_xlsx_source_rows",
]
