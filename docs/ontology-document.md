# Deterministic ontology document composition

`coms.ontology_document` composes one complete deterministic Turtle document
from two existing authorities:

```text
publication configuration + optional formal release context
        -> publication header renderer

caller-selected GovernedMappingRecord values
        -> single-record mapping compiler

header bytes + sorted active mapping statement bytes
        -> complete ontology document bytes
```

The composer uses the publication header bytes unchanged. Because that header
and every active mapping statement already end in exactly one LF, the sorted
statements follow the header immediately with no additional separator. An
explicit blank contributes no statement, so an all-blank collection produces
the existing header bytes exactly. The complete document ends in exactly one
LF.

Ordering is lexicographic over the already-canonical compiled statement bytes.
This makes input collection order irrelevant without introducing another
semantic canonicalization scheme or changing expression and property-chain
internals. Byte-identical active statements are rejected as duplicates rather
than emitted twice or silently deduplicated.

The caller decides which records belong in the ontology. This layer does not
apply product-membership policy, read source formats, write files, create
manifests or archives, package releases, load ontologies, or run reasoners.
Future product compilation may select records using configuration, but that
policy is outside this composition boundary.
