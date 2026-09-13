# COMS Publication Metadata Core

## Architectural boundary

COMS publication metadata is divided into mechanism and project policy.

The framework owns reusable mechanics such as:

- immutable ordered ontology-annotation values;
- structural validation of annotation object kinds;
- deterministic literal and IRI object rendering;
- release-version IRI construction;
- development and formal import resolution;
- later deterministic ontology-header assembly.

Project configuration owns publication policy such as:

- which annotation predicates are emitted;
- annotation order;
- which configured or release-context values supply annotation objects;
- whether an annotation applies to development output, formal output, or both;
- whether an object is an IRI, plain literal, language literal, or typed
  literal;
- language tags and datatype IRIs;
- product-specific applicability;
- prefix and compact-rendering policy.

COMS therefore does not define a universal fixed ontology-metadata vocabulary.

## OntologyAnnotation

`OntologyAnnotation` is the project-neutral intermediate value used by later
publication-policy evaluation and serialization.

It contains:

- `predicate_iri`;
- `object_kind`;
- `value`;
- optional `language`;
- optional `datatype_iri`.

Supported object kinds are:

- `iri`;
- `plain_literal`;
- `language_literal`;
- `typed_literal`.

The value object deliberately does not contain a product key or ontology
subject. Later publication assembly associates ordered annotations with the
configured product ontology identity.

## Structural validation

`ontology_annotation_issues` checks only object-shape consistency:

- IRI objects have neither language nor datatype;
- plain literals have neither language nor datatype;
- language literals require a language tag and prohibit a datatype;
- typed literals require a datatype IRI and prohibit a language tag.

This layer does not validate:

- absolute-IRI syntax;
- language-tag syntax;
- whether a predicate is approved by a project;
- whether a value is semantically appropriate for a predicate;
- whether a configured publication value is present;
- ontology graph semantics.

Those concerns belong to policy/configuration validation or later RDF
validation layers.

## Deterministic object rendering

`render_annotation_object_turtle` renders only the annotation object term.

It uses full IRIs for IRI and datatype terms and deterministic JSON-style
string escaping for literal lexical forms.

Predicate rendering, prefix selection, prefix compaction, complete triple
assembly, and ontology-header byte rendering are intentionally deferred until
the annotation-policy layer has been defined.

## Declarative annotation rules

`PublicationProfile.annotation_rules` is an ordered tuple of project policy.

Each rule configures:

- predicate IRI;
- object kind;
- development/formal applicability;
- exactly one configured value source or fixed value;
- optional language tag;
- optional datatype IRI;
- optional product-key scope.

Rule order is semantically significant and becomes annotation order when rules
are evaluated.

The framework defines a finite set of value-source identifiers so configuration
errors are detected before publication. Some sources are scalar and some are
multi-valued; rule evaluation will later expand multi-valued sources
deterministically.

Release-context value sources and the derived product release-version IRI are
formal-only. They cannot be used by rules that apply to development output.

This configuration layer still does not evaluate rules or assemble ontology
headers.

## Value-source cardinality and availability

Rule evaluation uses an explicit cardinality contract.

Fixed values and ordinary value sources are scalar. A scalar rule yields one
annotation.

`publication.creators` and `publication.contributors` are the only
multi-valued sources. They preserve configured tuple order and expand to one
annotation per value. An empty tuple is valid and expands to no annotations.

An explicitly requested optional scalar source must exist. Configuration
validation therefore rejects rules whose required publication or product value
is unavailable rather than treating absence as an implicit request to omit the
annotation.

`product_labels` and `product_descriptions` are keyed publication data. Each
collection may contain at most one record for a given product key. A rule using
`product.label` or `product.description` requires the corresponding keyed value
for every product in that rule's effective scope.

Release-context sources remain runtime values supplied by a validated formal
release context.
