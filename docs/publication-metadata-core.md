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
