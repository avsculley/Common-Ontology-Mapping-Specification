"""Project-neutral governed mapping records."""

from __future__ import annotations

from dataclasses import dataclass

from .mapping_expression import (
    ExpressionNode,
)


@dataclass(
    frozen=True,
)
class GovernedMappingRecord:
    """One resolved COMS mapping record independent of its source format."""

    row_id: str
    subject_iri: str
    predicate_iri: str | None
    mapping_type: str
    reasoning: str = ""
    expression: ExpressionNode | None = None
    target_property_iri: str | None = None
    property_chain: tuple[str, ...] = ()

    @property
    def target_source_count(
        self,
    ) -> int:
        """Return the number of represented semantic target forms."""

        return sum(
            (
                self.expression
                is not None,
                self.target_property_iri
                is not None,
                bool(
                    self.property_chain
                ),
            )
        )
