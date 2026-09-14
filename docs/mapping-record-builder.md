# Mapping-record builder

`coms.mapping_record_builder` connects already-resolved source identity to the
governed semantic record:

```text
source adapter
-> mapping-record builder
-> GovernedMappingRecord
-> canonical identity / future ontology compiler
```

The source adapter remains responsible for source-token resolution and for
supplying the subject IRI and entity kind. Target class expressions and
property chains use the generic parser/resolver contract.

The builder classifies only the OWL/RDFS predicates currently supported by the
COMS canonical authoritative-axiom layer. It produces class mappings, object
property mappings, property chains, domains, ranges, and explicit blanks. It
does not load workbooks or ontology graphs and does not compile or serialize
ontology axioms; compilation remains a subsequent layer.

The shared predicate IRIs live in `coms.mapping_predicates` so the builder and
canonical-identity layer use one authority. They remain available from
`coms.row_identity` for compatibility.
