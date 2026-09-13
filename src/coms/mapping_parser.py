"""Project-neutral parsing of resolved COMS mapping target syntax."""

from __future__ import annotations

import re
from typing import Protocol

from .mapping_expression import (
    ExpressionNode,
)


ENTITY_CLASS = "class"
ENTITY_OBJECT_PROPERTY = "object_property"

_TOKEN_RE = re.compile(
    r"\s*(\(|\)|[^\s()]+)"
)


class EntityResolutionError(ValueError):
    """A source adapter cannot resolve one entity token as the required kind."""


class MappingParseError(ValueError):
    """Mapping target syntax cannot be parsed into COMS semantic structure."""


class EntityResolver(Protocol):
    """Resolve source-format entity tokens to full IRIs."""

    def resolve_entity(
        self,
        token: str,
        expected_kind: str,
    ) -> str:
        """Resolve one token as the requested semantic entity kind."""
        ...


class ClassExpressionParser:
    """Parse the COMS class-expression compatibility grammar."""

    def __init__(
        self,
        text: str,
        resolver: EntityResolver,
    ):
        self.text = text
        self.resolver = resolver
        self.tokens = self._tokenize(
            text
        )
        self.position = 0

    @staticmethod
    def _tokenize(
        text: str,
    ) -> tuple[str, ...]:
        tokens: list[str] = []
        cursor = 0

        while cursor < len(
            text
        ):
            match = _TOKEN_RE.match(
                text,
                cursor,
            )

            if match is None:
                if not text[
                    cursor:
                ].strip():
                    break

                excerpt = text[
                    cursor:
                    cursor + 30
                ]

                raise MappingParseError(
                    "malformed class expression near "
                    f"{excerpt!r}"
                )

            tokens.append(
                match.group(
                    1
                )
            )
            cursor = match.end()

        return tuple(
            tokens
        )

    def parse(
        self,
    ) -> ExpressionNode:
        """Parse the complete target expression."""

        if not self.tokens:
            raise MappingParseError(
                "blank class expression"
            )

        expression = self._parse_or()

        remaining = self._peek()

        if remaining is not None:
            raise MappingParseError(
                "unexpected token "
                f"{remaining!r}"
            )

        return expression

    def _peek(
        self,
    ) -> str | None:
        if self.position >= len(
            self.tokens
        ):
            return None

        return self.tokens[
            self.position
        ]

    def _consume(
        self,
        expected: str | None = None,
    ) -> str:
        token = self._peek()

        if token is None:
            raise MappingParseError(
                "unexpected end of expression"
            )

        if (
            expected is not None
            and token != expected
        ):
            raise MappingParseError(
                f"expected {expected!r}, "
                f"found {token!r}"
            )

        self.position += 1
        return token

    def _parse_or(
        self,
    ) -> ExpressionNode:
        children = [
            self._parse_and()
        ]

        while self._peek() == "or":
            self._consume(
                "or"
            )
            children.append(
                self._parse_and()
            )

        if len(
            children
        ) == 1:
            return children[
                0
            ]

        return ExpressionNode(
            kind="union",
            children=tuple(
                children
            ),
        )

    def _parse_and(
        self,
    ) -> ExpressionNode:
        children = [
            self._parse_primary()
        ]

        while self._peek() == "and":
            self._consume(
                "and"
            )
            children.append(
                self._parse_primary()
            )

        if len(
            children
        ) == 1:
            return children[
                0
            ]

        return ExpressionNode(
            kind="intersection",
            children=tuple(
                children
            ),
        )

    def _parse_primary(
        self,
    ) -> ExpressionNode:
        token = self._peek()

        if token == "(":
            self._consume(
                "("
            )
            expression = (
                self._parse_or()
            )
            self._consume(
                ")"
            )
            return expression

        if token is None:
            raise MappingParseError(
                "unexpected end of expression"
            )

        if token in {
            ")",
            "and",
            "or",
            "some",
        }:
            raise MappingParseError(
                "expected entity token or "
                "parenthesized expression, "
                f"found {token!r}"
            )

        entity_token = self._consume()

        if self._peek() == "some":
            self._consume(
                "some"
            )

            property_iri = (
                self.resolver.resolve_entity(
                    entity_token,
                    ENTITY_OBJECT_PROPERTY,
                )
            )

            filler = (
                self._parse_primary()
            )

            return ExpressionNode(
                kind="some",
                property_iri=(
                    property_iri
                ),
                filler=filler,
            )

        iri = (
            self.resolver.resolve_entity(
                entity_token,
                ENTITY_CLASS,
            )
        )

        return ExpressionNode(
            kind="named",
            iri=iri,
        )


def parse_class_expression(
    text: str,
    resolver: EntityResolver,
) -> ExpressionNode:
    """Parse one class-expression target directly to the COMS expression model."""

    return ClassExpressionParser(
        text,
        resolver,
    ).parse()


def parse_property_chain(
    text: str,
    resolver: EntityResolver,
) -> tuple[str, ...]:
    """Parse an ordered object-property chain using ``o`` as the separator."""

    tokens = tuple(
        token
        for token
        in re.split(
            r"\s+",
            text.strip(),
        )
        if token
    )

    if (
        len(tokens) < 3
        or len(tokens) % 2 == 0
    ):
        raise MappingParseError(
            "invalid property-chain syntax "
            f"{text!r}"
        )

    chain: list[str] = []

    for index, token in enumerate(
        tokens
    ):
        if index % 2 == 1:
            if token != "o":
                raise MappingParseError(
                    "property-chain separator "
                    "must be 'o', "
                    f"found {token!r}"
                )

            continue

        chain.append(
            resolver.resolve_entity(
                token,
                ENTITY_OBJECT_PROPERTY,
            )
        )

    if len(
        chain
    ) < 2:
        raise MappingParseError(
            "property chains must contain "
            "at least two properties"
        )

    return tuple(
        chain
    )
