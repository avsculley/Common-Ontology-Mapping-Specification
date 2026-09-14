from pathlib import Path
import re
import unittest

from coms.mapping_expression import (
    ExpressionNode,
    canonicalize_expression,
)
from coms.mapping_parser import (
    ENTITY_CLASS,
    ENTITY_OBJECT_PROPERTY,
    EntityResolutionError,
    MappingParseError,
    parse_class_expression,
    parse_property_chain,
)


class DictResolver:
    def __init__(
        self,
        values: dict[
            tuple[str, str],
            str,
        ],
    ):
        self.values = values
        self.calls: list[
            tuple[str, str]
        ] = []

    def resolve_entity(
        self,
        token: str,
        expected_kind: str,
    ) -> str:
        self.calls.append(
            (
                token,
                expected_kind,
            )
        )

        key = (
            token,
            expected_kind,
        )

        if key not in self.values:
            raise EntityResolutionError(
                f"cannot resolve {token!r} "
                f"as {expected_kind}"
            )

        return self.values[
            key
        ]


class MappingParserTests(
    unittest.TestCase
):
    def test_named_expression_delegates_class_resolution(
        self,
    ):
        resolver = DictResolver(
            {
                (
                    "ex:Target",
                    ENTITY_CLASS,
                ): "urn:example:Target",
            }
        )

        expression = (
            parse_class_expression(
                "ex:Target",
                resolver,
            )
        )

        self.assertEqual(
            expression,
            ExpressionNode(
                kind="named",
                iri="urn:example:Target",
            ),
        )

        self.assertEqual(
            resolver.calls,
            [
                (
                    "ex:Target",
                    ENTITY_CLASS,
                ),
            ],
        )

    def test_and_precedes_or(
        self,
    ):
        resolver = DictResolver(
            {
                (
                    "ex:A",
                    ENTITY_CLASS,
                ): "urn:example:A",
                (
                    "ex:B",
                    ENTITY_CLASS,
                ): "urn:example:B",
                (
                    "ex:C",
                    ENTITY_CLASS,
                ): "urn:example:C",
            }
        )

        expression = (
            parse_class_expression(
                "ex:A or ex:B and ex:C",
                resolver,
            )
        )

        self.assertEqual(
            expression.kind,
            "union",
        )

        self.assertEqual(
            expression.children[
                0
            ].kind,
            "named",
        )

        self.assertEqual(
            expression.children[
                1
            ].kind,
            "intersection",
        )

    def test_parentheses_override_precedence(
        self,
    ):
        resolver = DictResolver(
            {
                (
                    "ex:A",
                    ENTITY_CLASS,
                ): "urn:example:A",
                (
                    "ex:B",
                    ENTITY_CLASS,
                ): "urn:example:B",
                (
                    "ex:C",
                    ENTITY_CLASS,
                ): "urn:example:C",
            }
        )

        expression = (
            parse_class_expression(
                "(ex:A or ex:B) and ex:C",
                resolver,
            )
        )

        self.assertEqual(
            expression.kind,
            "intersection",
        )

        self.assertEqual(
            expression.children[
                0
            ].kind,
            "union",
        )

    def test_existential_resolves_property_and_filler_kinds(
        self,
    ):
        resolver = DictResolver(
            {
                (
                    "ex:hasPart",
                    ENTITY_OBJECT_PROPERTY,
                ): "urn:example:hasPart",
                (
                    "ex:Part",
                    ENTITY_CLASS,
                ): "urn:example:Part",
            }
        )

        expression = (
            parse_class_expression(
                "ex:hasPart some ex:Part",
                resolver,
            )
        )

        self.assertEqual(
            expression,
            ExpressionNode(
                kind="some",
                property_iri=(
                    "urn:example:hasPart"
                ),
                filler=ExpressionNode(
                    kind="named",
                    iri="urn:example:Part",
                ),
            ),
        )

        self.assertEqual(
            resolver.calls,
            [
                (
                    "ex:hasPart",
                    ENTITY_OBJECT_PROPERTY,
                ),
                (
                    "ex:Part",
                    ENTITY_CLASS,
                ),
            ],
        )

    def test_nested_expression_flows_into_existing_canonicalizer(
        self,
    ):
        resolver = DictResolver(
            {
                (
                    "ex:Material",
                    ENTITY_CLASS,
                ): "urn:example:Material",
                (
                    "ex:hasFunction",
                    ENTITY_OBJECT_PROPERTY,
                ): "urn:example:hasFunction",
                (
                    "ex:Sensing",
                    ENTITY_CLASS,
                ): "urn:example:Sensing",
            }
        )

        expression = (
            parse_class_expression(
                (
                    "ex:Material and "
                    "(ex:hasFunction some ex:Sensing)"
                ),
                resolver,
            )
        )

        self.assertEqual(
            canonicalize_expression(
                expression
            ),
            (
                "ObjectIntersectionOf("
                "<urn:example:Material> "
                "ObjectSomeValuesFrom("
                "<urn:example:hasFunction> "
                "<urn:example:Sensing>"
                ")"
                ")"
            ),
        )

    def test_blank_and_structurally_invalid_expressions_are_rejected(
        self,
    ):
        resolver = DictResolver(
            {
                (
                    "ex:A",
                    ENTITY_CLASS,
                ): "urn:example:A",
                (
                    "ex:B",
                    ENTITY_CLASS,
                ): "urn:example:B",
            }
        )

        cases = (
            (
                "",
                "blank class expression",
            ),
            (
                "and",
                "expected entity token",
            ),
            (
                "(ex:A",
                "unexpected end of expression",
            ),
            (
                "ex:A ex:B",
                "unexpected token",
            ),
        )

        for text, message in cases:
            with self.subTest(
                text=text
            ):
                with self.assertRaisesRegex(
                    MappingParseError,
                    message,
                ):
                    parse_class_expression(
                        text,
                        resolver,
                    )

    def test_resolution_error_remains_distinct_from_parse_error(
        self,
    ):
        resolver = DictResolver(
            {}
        )

        with self.assertRaises(
            EntityResolutionError
        ):
            parse_class_expression(
                "missing:Class",
                resolver,
            )

    def test_property_chain_preserves_order_and_resolves_properties(
        self,
    ):
        resolver = DictResolver(
            {
                (
                    "ex:first",
                    ENTITY_OBJECT_PROPERTY,
                ): "urn:example:first",
                (
                    "ex:second",
                    ENTITY_OBJECT_PROPERTY,
                ): "urn:example:second",
                (
                    "ex:third",
                    ENTITY_OBJECT_PROPERTY,
                ): "urn:example:third",
            }
        )

        chain = parse_property_chain(
            (
                "ex:first o "
                "ex:second o "
                "ex:third"
            ),
            resolver,
        )

        self.assertEqual(
            chain,
            (
                "urn:example:first",
                "urn:example:second",
                "urn:example:third",
            ),
        )

        self.assertEqual(
            resolver.calls,
            [
                (
                    "ex:first",
                    ENTITY_OBJECT_PROPERTY,
                ),
                (
                    "ex:second",
                    ENTITY_OBJECT_PROPERTY,
                ),
                (
                    "ex:third",
                    ENTITY_OBJECT_PROPERTY,
                ),
            ],
        )

    def test_property_chain_requires_o_separator(
        self,
    ):
        resolver = DictResolver(
            {
                (
                    "ex:first",
                    ENTITY_OBJECT_PROPERTY,
                ): "urn:example:first",
                (
                    "ex:second",
                    ENTITY_OBJECT_PROPERTY,
                ): "urn:example:second",
            }
        )

        with self.assertRaisesRegex(
            MappingParseError,
            "separator must be 'o'",
        ):
            parse_property_chain(
                "ex:first x ex:second",
                resolver,
            )

    def test_property_chain_requires_two_properties(
        self,
    ):
        resolver = DictResolver(
            {
                (
                    "ex:first",
                    ENTITY_OBJECT_PROPERTY,
                ): "urn:example:first",
            }
        )

        with self.assertRaisesRegex(
            MappingParseError,
            "invalid property-chain syntax",
        ):
            parse_property_chain(
                "ex:first",
                resolver,
            )

    def test_module_is_project_and_source_format_neutral(
        self,
    ):
        source = Path(
            "src/coms/mapping_parser.py"
        ).read_text(
            encoding="utf-8"
        )

        for token in (
            "openpyxl",
            "rdflib",
            "Workbook",
            "Worksheet",
            "URIRef",
            "Graph",
        ):
            self.assertNotIn(
                token,
                source,
            )

        pattern = re.compile(
            r"\b(?:SSN|SOSA|PROV|BFO|CCO|RO|HermiT)\b",
            re.IGNORECASE,
        )

        self.assertIsNone(
            pattern.search(
                source
            )
        )
