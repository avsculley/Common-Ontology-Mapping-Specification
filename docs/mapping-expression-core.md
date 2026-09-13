# Mapping expression core

`coms.mapping_expression` owns the project-neutral expression algebra used by
governed COMS mapping rows.

The module is extracted from the previously proven `row_identity` machinery.
The extraction changes module boundaries, not canonical expression semantics.

## ExpressionNode

`ExpressionNode` is the immutable recursive representation of one class
expression.

The currently supported node kinds are:

- `named` — one named class IRI;
- `intersection` — an object intersection;
- `union` — an object union;
- `some` — an existential object-property restriction.

Intersections and unions are recursively flattened, deduplicated by canonical
representation, and lexically sorted. A single unique operand collapses to
that operand.

Property-chain expressions are intentionally not `ExpressionNode` values.
They are mapping-row target forms whose order is semantically significant and
remain governed by `row_identity`.

## Canonical representation

`canonicalize_expression` emits deterministic OWL functional-style terms:

- named classes become `<IRI>`;
- intersections become `ObjectIntersectionOf(...)`;
- unions become `ObjectUnionOf(...)`;
- existential restrictions become `ObjectSomeValuesFrom(...)`.

IRI lexical values are normalized to Unicode NFC before rendering.

The expression module does not know about:

- workbook locations;
- RowIDs;
- mapping predicates;
- mapping types;
- explicit blank rows;
- property mapping targets;
- property chains;
- authoritative-axiom identity;
- duplicate-row or duplicate-axiom diagnostics.

Those remain row-governance concerns in `coms.row_identity`.

## Compatibility boundary

`coms.row_identity.ExpressionNode` remains available as the imported
`coms.mapping_expression.ExpressionNode` class so existing consumers do not
need to migrate immediately.

`row_identity` converts `MappingExpressionError` into its established
row-located `UNSUPPORTED_CANONICAL_EXPRESSION` diagnostic. Existing canonical
row JSON, expression hashes, and authoritative axiom identities therefore
remain unchanged by this extraction.

This module is still an intermediate representation and canonicalization layer.
It does not parse workbook syntax and does not emit RDF/OWL graphs. Those are
separate future parser and compiler layers.
