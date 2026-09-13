import unittest

from coms import mapping_expression as expression
from coms import row_identity as identity


def named(
    iri: str,
) -> expression.ExpressionNode:
    return expression.ExpressionNode(
        kind="named",
        iri=iri,
    )


def intersection(
    *children: expression.ExpressionNode,
) -> expression.ExpressionNode:
    return expression.ExpressionNode(
        kind="intersection",
        children=children,
    )


def union(
    *children: expression.ExpressionNode,
) -> expression.ExpressionNode:
    return expression.ExpressionNode(
        kind="union",
        children=children,
    )


def some(
    property_iri: str,
    filler: expression.ExpressionNode,
) -> expression.ExpressionNode:
    return expression.ExpressionNode(
        kind="some",
        property_iri=property_iri,
        filler=filler,
    )


class MappingExpressionTests(
    unittest.TestCase
):
    def test_row_identity_reexports_exact_expression_node_type(
        self,
    ):
        self.assertIs(
            identity.ExpressionNode,
            expression.ExpressionNode,
        )

    def test_named_expression_normalizes_unicode_to_nfc(
        self,
    ):
        value = (
            expression.canonicalize_expression(
                named(
                    "urn:example:e\u0301"
                )
            )
        )

        self.assertEqual(
            value,
            "<urn:example:é>",
        )

    def test_intersection_flattens_deduplicates_and_sorts(
        self,
    ):
        value = (
            expression.canonicalize_expression(
                intersection(
                    named(
                        "urn:example:Z"
                    ),
                    intersection(
                        named(
                            "urn:example:A"
                        ),
                        named(
                            "urn:example:Z"
                        ),
                    ),
                )
            )
        )

        self.assertEqual(
            value,
            (
                "ObjectIntersectionOf("
                "<urn:example:A> "
                "<urn:example:Z>"
                ")"
            ),
        )

    def test_union_flattens_deduplicates_and_sorts(
        self,
    ):
        value = (
            expression.canonicalize_expression(
                union(
                    named(
                        "urn:example:B"
                    ),
                    union(
                        named(
                            "urn:example:A"
                        ),
                        named(
                            "urn:example:B"
                        ),
                    ),
                )
            )
        )

        self.assertEqual(
            value,
            (
                "ObjectUnionOf("
                "<urn:example:A> "
                "<urn:example:B>"
                ")"
            ),
        )

    def test_existential_restriction_preserves_role_and_canonicalizes_filler(
        self,
    ):
        value = (
            expression.canonicalize_expression(
                some(
                    "urn:example:has-part",
                    intersection(
                        named(
                            "urn:example:B"
                        ),
                        named(
                            "urn:example:A"
                        ),
                    ),
                )
            )
        )

        self.assertEqual(
            value,
            (
                "ObjectSomeValuesFrom("
                "<urn:example:has-part> "
                "ObjectIntersectionOf("
                "<urn:example:A> "
                "<urn:example:B>"
                ")"
                ")"
            ),
        )

    def test_structural_expression_failures_are_generic(
        self,
    ):
        cases = (
            (
                expression.ExpressionNode(
                    kind="named",
                ),
                "named expression lacks an IRI",
            ),
            (
                expression.ExpressionNode(
                    kind="intersection",
                ),
                (
                    "intersection expression "
                    "has no operands"
                ),
            ),
            (
                expression.ExpressionNode(
                    kind="some",
                    property_iri=(
                        "urn:example:p"
                    ),
                ),
                (
                    "existential restriction lacks "
                    "a property or filler"
                ),
            ),
            (
                expression.ExpressionNode(
                    kind="unsupported",
                ),
                (
                    "unsupported expression node "
                    "kind 'unsupported'"
                ),
            ),
        )

        for node, message in cases:
            with self.subTest(
                kind=node.kind
            ):
                with self.assertRaisesRegex(
                    expression.MappingExpressionError,
                    message.replace(
                        "'",
                        r"\'",
                    ),
                ):
                    expression.canonicalize_expression(
                        node
                    )

    def test_empty_iri_retains_existing_value_error_contract(
        self,
    ):
        with self.assertRaisesRegex(
            ValueError,
            "IRI must be nonempty",
        ):
            expression.canonicalize_expression(
                named(
                    ""
                )
            )
