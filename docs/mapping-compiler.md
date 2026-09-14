# Deterministic mapping compiler

`coms.mapping_compiler` renders one existing `GovernedMappingRecord` directly
as deterministic, full-IRI RDF/Turtle bytes:

```text
GovernedMappingRecord
        |
        +----> canonical semantic identity (`row_identity`)
        |
        +----> deterministic RDF/Turtle (`mapping_compiler`)
```

These are independent representations of the same governed mapping semantics.
The compiler uses the established expression canonicalizer to flatten,
deduplicate, collapse, and order boolean class-expression operands before
rendering inline Turtle blank-node and list syntax. An active record produces
one complete statement ending in one LF; an explicit blank produces no bytes.

This increment does not assemble multiple records into a product, add ontology
headers or publication metadata, choose product membership, write files, run a
reasoner, or construct releases or packages.
