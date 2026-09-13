# Mapping parser and resolver core

`coms.mapping_parser` defines the source-neutral boundary between textual
mapping syntax and resolved COMS semantic objects.

The pipeline is:

```text
source-format token/text
        |
        v
EntityResolver
        |
        +----> full class/property IRIs
        |
        v
class-expression / property-chain parser
        |
        v
ExpressionNode or ordered property IRI tuple
        |
        v
GovernedMappingRecord
```

## Entity resolution

`EntityResolver` is a protocol rather than an ontology-loading implementation.

Its contract is:

```text
resolve_entity(token, expected_kind) -> full IRI string
```

The two entity kinds currently required by the mapping grammar are:

- `class`
- `object_property`

A resolver implementation decides what source tokens mean. It may support
CURIE expansion, exact IRI lookup, labels, local ontology inspection, remote
registries, or some other project policy.

The parser deliberately does not know how resolution is implemented.

`EntityResolutionError` is distinct from `MappingParseError`. Failure to
resolve a valid token is therefore distinguishable from malformed mapping
syntax.

## Class-expression grammar

The extracted compatibility grammar supports:

```text
expression  := or-expression
or-expression
            := and-expression ("or" and-expression)*
and-expression
            := primary ("and" primary)*
primary     := "(" expression ")"
             | entity-token
             | property-token "some" primary
```

This produces the existing project-neutral `ExpressionNode` kinds:

- `named`
- `intersection`
- `union`
- `some`

`and` binds more tightly than `or`. Parentheses override precedence.

The parser constructs `ExpressionNode` directly. The intermediate RDFLib-based
expression model used by the SSN reference implementation is not part of the
COMS architecture.

## Property chains

Property-chain syntax is an ordered sequence such as:

```text
ex:hasParent o ex:hasParent
```

Each term is resolved as an object property. The resulting tuple preserves the
configured order because property-chain order is semantically significant.

## Deliberate exclusions

This module does not:

- open workbooks;
- load RDF graphs;
- inspect ontology declarations;
- define prefix mappings;
- perform label matching;
- restrict source entities to particular ontology families;
- classify predicates into COMS mapping types;
- construct `GovernedMappingRecord`;
- emit RDF or OWL.

Those responsibilities belong to configuration, source adapters, the future
record builder, or the future ontology compiler.

In particular, SSN/SOSA-specific source-prefix restrictions and local ontology
graph loading remain reference-project adapter behavior rather than COMS core
behavior.
