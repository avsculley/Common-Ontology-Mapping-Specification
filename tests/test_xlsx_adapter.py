import ast
from dataclasses import FrozenInstanceError
from pathlib import Path
import re
from tempfile import TemporaryDirectory
import unittest
from unittest import mock

import openpyxl

from coms.adapters.xlsx import (
    WorkbookSourceRow,
    XlsxAdapterDependencyError,
    XlsxAdapterError,
    read_xlsx_source_rows,
)
from coms.config import (
    HeaderBinding,
    WorkbookProfile,
)
from coms.row_identity import RowLocation


CORE_HEADERS = (
    "sssom:subject_id",
    "sssom:predicate_id",
    "coms:Target",
    "coms:Reasoning",
    "coms:RowID",
)

STATUS_HEADER = "coms:MappingStatus"

ROW_ID = (
    "urn:uuid:11111111-1111-4111-8111-111111111111"
)


class XlsxAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = TemporaryDirectory(
            prefix="coms-xlsx-adapter-"
        )
        self.addCleanup(
            self.temporary_directory.cleanup
        )
        self.root = Path(
            self.temporary_directory.name
        )

    def workbook(
        self,
        sheets: tuple[
            tuple[
                str,
                tuple[str, ...],
                tuple[tuple[object, ...], ...],
            ],
            ...,
        ],
        *,
        name: str = "mapping.xlsx",
    ) -> Path:
        path = self.root / name
        workbook = openpyxl.Workbook()

        for index, (
            sheet_name,
            headers,
            rows,
        ) in enumerate(sheets):
            worksheet = (
                workbook.active
                if index == 0
                else workbook.create_sheet()
            )
            worksheet.title = sheet_name
            worksheet.append(list(headers))

            for row in rows:
                worksheet.append(list(row))

        workbook.save(path)
        workbook.close()
        return path

    def profile(
        self,
        path: Path | str,
        *,
        selectors: tuple[str, ...] = (),
        bindings: tuple[HeaderBinding, ...] = (),
        required_columns: tuple[str, ...] = CORE_HEADERS,
        row_id_column: str = "coms:RowID",
    ) -> WorkbookProfile:
        return WorkbookProfile(
            workbook_path=str(path),
            sheet_selectors=selectors,
            header_bindings=bindings,
            required_columns=required_columns,
            optional_columns=(STATUS_HEADER,),
            row_id_column=row_id_column,
        )

    @staticmethod
    def canonical_row(
        subject: object = "ex:Source",
        predicate: object = "rdfs:subClassOf",
        target: object = "ex:Target",
        reasoning: object = "because",
        row_id: object = ROW_ID,
    ) -> tuple[object, ...]:
        return (
            subject,
            predicate,
            target,
            reasoning,
            row_id,
        )

    def test_one_governed_sheet_with_canonical_headers(self):
        path = self.workbook(
            (
                (
                    "Mappings",
                    CORE_HEADERS,
                    (self.canonical_row(),),
                ),
            )
        )

        rows = read_xlsx_source_rows(
            self.profile(path)
        )

        self.assertEqual(
            rows,
            (
                WorkbookSourceRow(
                    location=RowLocation(
                        "Mappings",
                        2,
                    ),
                    row_id_text=ROW_ID,
                    subject_text="ex:Source",
                    predicate_text=(
                        "rdfs:subClassOf"
                    ),
                    target_text="ex:Target",
                    reasoning_text="because",
                    status_text=None,
                ),
            ),
        )

    def test_multiple_governed_sheets_are_extracted(self):
        path = self.workbook(
            (
                (
                    "Classes",
                    CORE_HEADERS,
                    (self.canonical_row("ex:Class"),),
                ),
                (
                    "Properties",
                    CORE_HEADERS,
                    (self.canonical_row("ex:Property"),),
                ),
            )
        )

        rows = read_xlsx_source_rows(
            self.profile(path)
        )

        self.assertEqual(
            [row.subject_text for row in rows],
            ["ex:Class", "ex:Property"],
        )

    def test_configured_selector_order_is_authoritative(self):
        path = self.workbook(
            (
                (
                    "First",
                    CORE_HEADERS,
                    (self.canonical_row("ex:First"),),
                ),
                (
                    "Second",
                    CORE_HEADERS,
                    (self.canonical_row("ex:Second"),),
                ),
            )
        )

        rows = read_xlsx_source_rows(
            self.profile(
                path,
                selectors=("Second", "First"),
            )
        )

        self.assertEqual(
            [row.location.worksheet for row in rows],
            ["Second", "First"],
        )

    def test_discovery_preserves_physical_sheet_order(self):
        path = self.workbook(
            (
                (
                    "Second",
                    CORE_HEADERS,
                    (self.canonical_row("ex:Second"),),
                ),
                (
                    "First",
                    CORE_HEADERS,
                    (self.canonical_row("ex:First"),),
                ),
            )
        )

        rows = read_xlsx_source_rows(
            self.profile(path)
        )

        self.assertEqual(
            [row.location.worksheet for row in rows],
            ["Second", "First"],
        )

    def test_discovery_requires_full_header_contract(self):
        headers_without_row_id = tuple(
            header
            for header in CORE_HEADERS
            if header != "coms:RowID"
        )
        required_headers = (
            *CORE_HEADERS,
            "ProjectRequired",
        )
        path = self.workbook(
            (
                (
                    "MissingRowID",
                    (
                        *headers_without_row_id,
                        "ProjectRequired",
                    ),
                    (("ex:Ignored", "p", "t", "r", "x"),),
                ),
                (
                    "MissingAdditional",
                    CORE_HEADERS,
                    (self.canonical_row("ex:Ignored"),),
                ),
                (
                    "Mappings",
                    required_headers,
                    (self.canonical_row() + ("x",),),
                ),
            )
        )

        rows = read_xlsx_source_rows(
            self.profile(
                path,
                required_columns=required_headers,
            )
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(
            rows[0].location.worksheet,
            "Mappings",
        )

    def test_duplicate_sheet_selectors_are_rejected(self):
        path = self.workbook(
            (
                (
                    "Mappings",
                    CORE_HEADERS,
                    (self.canonical_row(),),
                ),
            )
        )

        with self.assertRaisesRegex(
            XlsxAdapterError,
            "duplicate workbook sheet selectors: Mappings",
        ):
            read_xlsx_source_rows(
                self.profile(
                    path,
                    selectors=("Mappings", "Mappings"),
                )
            )

    def test_missing_selected_sheet_is_rejected(self):
        path = self.workbook(
            (
                (
                    "Mappings",
                    CORE_HEADERS,
                    (self.canonical_row(),),
                ),
            )
        )

        with self.assertRaisesRegex(
            XlsxAdapterError,
            "missing configured workbook sheets: Missing",
        ):
            read_xlsx_source_rows(
                self.profile(
                    path,
                    selectors=("Missing",),
                )
            )

    def test_no_governed_sheets_is_rejected(self):
        path = self.workbook(
            (
                (
                    "Notes",
                    ("Note",),
                    (("not governed",),),
                ),
            )
        )

        with self.assertRaisesRegex(
            XlsxAdapterError,
            "no governed worksheets found",
        ):
            read_xlsx_source_rows(
                self.profile(path)
            )

    def test_reordered_columns_preserve_field_values(self):
        headers = (
            "coms:Reasoning",
            "coms:RowID",
            "coms:Target",
            "sssom:subject_id",
            "sssom:predicate_id",
        )
        path = self.workbook(
            (
                (
                    "Mappings",
                    headers,
                    (
                        (
                            "because",
                            ROW_ID,
                            "ex:Target",
                            "ex:Source",
                            "rdfs:subClassOf",
                        ),
                    ),
                ),
            )
        )

        row = read_xlsx_source_rows(
            self.profile(path)
        )[0]

        self.assertEqual(
            (
                row.row_id_text,
                row.subject_text,
                row.predicate_text,
                row.target_text,
                row.reasoning_text,
            ),
            (
                ROW_ID,
                "ex:Source",
                "rdfs:subClassOf",
                "ex:Target",
                "because",
            ),
        )

    def test_custom_header_bindings_are_authoritative(self):
        headers = (
            "ID",
            "Source",
            "Predicate",
            "Target",
            "Reasoning",
            "Status",
        )
        path = self.workbook(
            (
                (
                    "Mappings",
                    headers,
                    (
                        (
                            ROW_ID,
                            "ex:Source",
                            "rdfs:subClassOf",
                            "ex:Target",
                            "because",
                            "opaque",
                        ),
                    ),
                ),
            )
        )
        fields = (
            "row_id",
            "source",
            "predicate",
            "target",
            "reasoning",
            "status",
        )
        bindings = tuple(
            HeaderBinding(field, header)
            for field, header in zip(fields, headers)
        )

        row = read_xlsx_source_rows(
            self.profile(
                path,
                bindings=bindings,
                required_columns=headers[:5],
                row_id_column="ID",
            )
        )[0]

        self.assertEqual(row.subject_text, "ex:Source")
        self.assertEqual(row.status_text, "opaque")

    def test_missing_required_header_is_rejected(self):
        headers = tuple(
            header
            for header in CORE_HEADERS
            if header != "coms:Reasoning"
        )
        path = self.workbook(
            (
                (
                    "Mappings",
                    headers,
                    (self.canonical_row()[:-1],),
                ),
            )
        )

        with self.assertRaisesRegex(
            XlsxAdapterError,
            "missing required headers: coms:Reasoning",
        ):
            read_xlsx_source_rows(
                self.profile(
                    path,
                    selectors=("Mappings",),
                )
            )

    def test_missing_configured_row_id_header_is_rejected(self):
        headers = CORE_HEADERS[:-1]
        path = self.workbook(
            (
                (
                    "Mappings",
                    headers,
                    (self.canonical_row()[:-1],),
                ),
            )
        )

        with self.assertRaisesRegex(
            XlsxAdapterError,
            "missing configured RowID header 'coms:RowID'",
        ):
            read_xlsx_source_rows(
                self.profile(
                    path,
                    selectors=("Mappings",),
                    required_columns=headers,
                )
            )

    def test_additional_configured_required_header_is_checked(self):
        path = self.workbook(
            (
                (
                    "Mappings",
                    CORE_HEADERS,
                    (self.canonical_row(),),
                ),
            )
        )

        with self.assertRaisesRegex(
            XlsxAdapterError,
            "missing required headers: ProjectRequired",
        ):
            read_xlsx_source_rows(
                self.profile(
                    path,
                    selectors=("Mappings",),
                    required_columns=(
                        *CORE_HEADERS,
                        "ProjectRequired",
                    ),
                )
            )

    def test_duplicate_governed_header_is_rejected(self):
        headers = (
            *CORE_HEADERS,
            "coms:Target",
        )
        path = self.workbook(
            (
                (
                    "Mappings",
                    headers,
                    (self.canonical_row() + ("duplicate",),),
                ),
            )
        )

        with self.assertRaisesRegex(
            XlsxAdapterError,
            "duplicate governed/configured headers: coms:Target",
        ):
            read_xlsx_source_rows(
                self.profile(path)
            )

    def test_ambiguous_header_bindings_are_rejected(self):
        path = self.workbook(
            (
                (
                    "Mappings",
                    CORE_HEADERS,
                    (self.canonical_row(),),
                ),
            )
        )

        with self.assertRaisesRegex(
            XlsxAdapterError,
            "ambiguous workbook header bindings",
        ):
            read_xlsx_source_rows(
                self.profile(
                    path,
                    bindings=(
                        HeaderBinding(
                            "source",
                            "sssom:subject_id",
                        ),
                        HeaderBinding(
                            "source",
                            "Source",
                        ),
                    ),
                )
            )

    def test_row_id_binding_must_match_row_id_column(self):
        path = self.workbook(
            (
                (
                    "Mappings",
                    CORE_HEADERS,
                    (self.canonical_row(),),
                ),
            )
        )

        with self.assertRaisesRegex(
            XlsxAdapterError,
            "row_id header binding must match row_id_column",
        ):
            read_xlsx_source_rows(
                self.profile(
                    path,
                    bindings=(
                        HeaderBinding(
                            "row_id",
                            "DifferentRowID",
                        ),
                    ),
                )
            )

    def test_unsupported_binding_field_is_rejected(self):
        path = self.workbook(
            (
                (
                    "Mappings",
                    CORE_HEADERS,
                    (self.canonical_row(),),
                ),
            )
        )

        with self.assertRaisesRegex(
            XlsxAdapterError,
            "unsupported workbook header binding fields: subject",
        ):
            read_xlsx_source_rows(
                self.profile(
                    path,
                    bindings=(
                        HeaderBinding(
                            "subject",
                            "sssom:subject_id",
                        ),
                    ),
                )
            )

    def test_optional_status_present_is_extracted_opaquely(self):
        headers = (*CORE_HEADERS, STATUS_HEADER)
        path = self.workbook(
            (
                (
                    "Mappings",
                    headers,
                    (
                        self.canonical_row()
                        + ("project-specific-state",),
                    ),
                ),
            )
        )

        row = read_xlsx_source_rows(
            self.profile(path)
        )[0]

        self.assertEqual(
            row.status_text,
            "project-specific-state",
        )

    def test_optional_status_absent_is_none(self):
        path = self.workbook(
            (
                (
                    "Mappings",
                    CORE_HEADERS,
                    (self.canonical_row(),),
                ),
            )
        )

        row = read_xlsx_source_rows(
            self.profile(path)
        )[0]

        self.assertIsNone(row.status_text)

    def test_none_cells_normalize_to_empty_strings(self):
        path = self.workbook(
            (
                (
                    "Mappings",
                    CORE_HEADERS,
                    (("ex:Source", None, None, None, None),),
                ),
            )
        )

        row = read_xlsx_source_rows(
            self.profile(path)
        )[0]

        self.assertEqual(
            (
                row.row_id_text,
                row.predicate_text,
                row.target_text,
                row.reasoning_text,
            ),
            ("", "", "", ""),
        )

    def test_surrounding_whitespace_is_trimmed(self):
        path = self.workbook(
            (
                (
                    "Mappings",
                    CORE_HEADERS,
                    (
                        self.canonical_row(
                            "  ex:Source  ",
                            " rdfs:subClassOf ",
                            "  ex:Target\n",
                            " because ",
                            f" {ROW_ID} ",
                        ),
                    ),
                ),
            )
        )

        row = read_xlsx_source_rows(
            self.profile(path)
        )[0]

        self.assertEqual(row.subject_text, "ex:Source")
        self.assertEqual(row.target_text, "ex:Target")
        self.assertEqual(row.row_id_text, ROW_ID)

    def test_wholly_blank_rows_are_skipped(self):
        path = self.workbook(
            (
                (
                    "Mappings",
                    CORE_HEADERS,
                    (
                        self.canonical_row("ex:First"),
                        (None, None, None, None, None),
                        self.canonical_row("ex:Second"),
                    ),
                ),
            )
        )

        rows = read_xlsx_source_rows(
            self.profile(path)
        )

        self.assertEqual(
            [row.subject_text for row in rows],
            ["ex:First", "ex:Second"],
        )
        self.assertEqual(
            [row.location.row_number for row in rows],
            [2, 4],
        )

    def test_subject_only_row_is_retained(self):
        path = self.workbook(
            (
                (
                    "Mappings",
                    CORE_HEADERS,
                    (("ex:Source", None, None, None, None),),
                ),
            )
        )

        rows = read_xlsx_source_rows(
            self.profile(path)
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].subject_text, "ex:Source")

    def test_row_id_only_malformed_row_is_retained(self):
        malformed_row_id = "not-a-canonical-row-id"
        path = self.workbook(
            (
                (
                    "Mappings",
                    CORE_HEADERS,
                    (
                        (
                            None,
                            None,
                            None,
                            None,
                            malformed_row_id,
                        ),
                    ),
                ),
            )
        )

        rows = read_xlsx_source_rows(
            self.profile(path)
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(
            rows[0].row_id_text,
            malformed_row_id,
        )

    def test_duplicate_row_ids_are_retained_for_downstream_validation(self):
        path = self.workbook(
            (
                (
                    "Mappings",
                    CORE_HEADERS,
                    (
                        self.canonical_row("ex:First"),
                        self.canonical_row("ex:Second"),
                    ),
                ),
            )
        )

        rows = read_xlsx_source_rows(
            self.profile(path)
        )

        self.assertEqual(len(rows), 2)
        self.assertEqual(
            [row.row_id_text for row in rows],
            [ROW_ID, ROW_ID],
        )

    def test_predicate_and_target_without_subject_are_retained(self):
        path = self.workbook(
            (
                (
                    "Mappings",
                    CORE_HEADERS,
                    (
                        (
                            None,
                            "rdfs:subClassOf",
                            "ex:Target",
                            None,
                            ROW_ID,
                        ),
                    ),
                ),
            )
        )

        row = read_xlsx_source_rows(
            self.profile(path)
        )[0]

        self.assertEqual(row.subject_text, "")
        self.assertEqual(
            row.predicate_text,
            "rdfs:subClassOf",
        )
        self.assertEqual(row.target_text, "ex:Target")

    def test_predicate_target_mismatches_are_retained(self):
        path = self.workbook(
            (
                (
                    "Mappings",
                    CORE_HEADERS,
                    (
                        (
                            None,
                            "rdfs:subClassOf",
                            None,
                            None,
                            None,
                        ),
                        (
                            None,
                            None,
                            "ex:Target",
                            None,
                            None,
                        ),
                    ),
                ),
            )
        )

        rows = read_xlsx_source_rows(
            self.profile(path)
        )

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].predicate_text, "rdfs:subClassOf")
        self.assertEqual(rows[1].target_text, "ex:Target")

    def test_reasoning_only_and_status_only_rows_are_retained(self):
        headers = (*CORE_HEADERS, STATUS_HEADER)
        path = self.workbook(
            (
                (
                    "Mappings",
                    headers,
                    (
                        (None, None, None, "reason", None, None),
                        (None, None, None, None, None, "pending"),
                    ),
                ),
            )
        )

        rows = read_xlsx_source_rows(
            self.profile(path)
        )

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].reasoning_text, "reason")
        self.assertEqual(rows[1].status_text, "pending")

    def test_unrelated_extra_column_is_ignored(self):
        headers = (*CORE_HEADERS, "Unrelated")
        path = self.workbook(
            (
                (
                    "Mappings",
                    headers,
                    (
                        self.canonical_row()
                        + ("ignored",),
                        (None, None, None, None, None, "only extra"),
                    ),
                ),
            )
        )

        rows = read_xlsx_source_rows(
            self.profile(path)
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].subject_text, "ex:Source")

    def test_formula_in_governed_cell_is_rejected(self):
        path = self.workbook(
            (
                (
                    "Mappings",
                    CORE_HEADERS,
                    (
                        self.canonical_row(
                            target="=1+1",
                        ),
                    ),
                ),
            )
        )

        with self.assertRaisesRegex(
            XlsxAdapterError,
            "formula is not allowed in governed field 'target'",
        ):
            read_xlsx_source_rows(
                self.profile(path)
            )

    def test_row_location_preserves_sheet_and_physical_row(self):
        path = self.workbook(
            (
                (
                    "Mappings",
                    CORE_HEADERS,
                    (
                        (None, None, None, None, None),
                        self.canonical_row(),
                    ),
                ),
            )
        )

        row = read_xlsx_source_rows(
            self.profile(path)
        )[0]

        self.assertEqual(
            row.location,
            RowLocation("Mappings", 3),
        )

    def test_extraction_is_repeatable(self):
        path = self.workbook(
            (
                (
                    "Mappings",
                    CORE_HEADERS,
                    (self.canonical_row(),),
                ),
            )
        )
        profile = self.profile(path)

        self.assertEqual(
            read_xlsx_source_rows(profile),
            read_xlsx_source_rows(profile),
        )

    def test_workbook_bytes_are_unchanged(self):
        path = self.workbook(
            (
                (
                    "Mappings",
                    CORE_HEADERS,
                    (self.canonical_row(),),
                ),
            )
        )
        before = path.read_bytes()

        read_xlsx_source_rows(
            self.profile(path)
        )

        self.assertEqual(path.read_bytes(), before)

    def test_workbook_mtime_is_unchanged(self):
        path = self.workbook(
            (
                (
                    "Mappings",
                    CORE_HEADERS,
                    (self.canonical_row(),),
                ),
            )
        )
        before = path.stat().st_mtime_ns

        read_xlsx_source_rows(
            self.profile(path)
        )

        self.assertEqual(path.stat().st_mtime_ns, before)

    def test_extraction_never_calls_save(self):
        path = self.workbook(
            (
                (
                    "Mappings",
                    CORE_HEADERS,
                    (self.canonical_row(),),
                ),
            )
        )

        with mock.patch.object(
            openpyxl.workbook.workbook.Workbook,
            "save",
            side_effect=AssertionError(
                "adapter must not save"
            ),
        ) as save:
            read_xlsx_source_rows(
                self.profile(path)
            )

        save.assert_not_called()

    def test_relative_workbook_path_uses_explicit_base_directory(self):
        path = self.workbook(
            (
                (
                    "Mappings",
                    CORE_HEADERS,
                    (self.canonical_row(),),
                ),
            ),
            name="relative.xlsx",
        )

        rows = read_xlsx_source_rows(
            self.profile(path.name),
            base_directory=self.root,
        )

        self.assertEqual(len(rows), 1)

    def test_source_row_is_frozen(self):
        row = WorkbookSourceRow(
            location=RowLocation("Mappings", 2),
            row_id_text=ROW_ID,
            subject_text="ex:Source",
            predicate_text="",
            target_text="",
            reasoning_text="",
            status_text=None,
        )

        with self.assertRaises(FrozenInstanceError):
            row.subject_text = "ex:Changed"

    def test_missing_openpyxl_has_adapter_specific_error(self):
        path = self.root / "unopened.xlsx"

        with (
            mock.patch(
                "coms.adapters.xlsx.import_module",
                side_effect=ModuleNotFoundError(
                    "No module named 'openpyxl'"
                ),
            ),
            self.assertRaisesRegex(
                XlsxAdapterDependencyError,
                "install the project with the 'xlsx' extra",
            ),
        ):
            read_xlsx_source_rows(
                self.profile(path)
            )

    def test_adapter_dependencies_and_policy_are_neutral(self):
        path = Path(
            "src/coms/adapters/xlsx.py"
        )
        source = path.read_text(
            encoding="utf-8"
        )
        tree = ast.parse(source)
        imported_roots = {
            alias.name.split(".", 1)[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        imported_roots.update(
            node.module.split(".", 1)[0]
            for node in ast.walk(tree)
            if (
                isinstance(node, ast.ImportFrom)
                and node.module
                and not node.level
            )
        )

        self.assertNotIn("openpyxl", imported_roots)
        self.assertNotIn("rdflib", imported_roots)
        self.assertIsNone(
            re.search(
                r"\b(?:SSN|SOSA|PROV|BFO|CCO|RO|HermiT)\b",
                source,
                flags=re.IGNORECASE,
            )
        )
        self.assertNotIn(
            "build_governed_mapping_record",
            source,
        )
        self.assertNotIn(
            "parse_class_expression",
            source,
        )


if __name__ == "__main__":
    unittest.main()
