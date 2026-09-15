"""Generic OWL/RDFS predicates supported by COMS mapping semantics."""


RDFS_SUBCLASS_OF = "http://www.w3.org/2000/01/rdf-schema#subClassOf"
RDFS_SUBPROPERTY_OF = "http://www.w3.org/2000/01/rdf-schema#subPropertyOf"
RDFS_DOMAIN = "http://www.w3.org/2000/01/rdf-schema#domain"
RDFS_RANGE = "http://www.w3.org/2000/01/rdf-schema#range"
OWL_EQUIVALENT_CLASS = "http://www.w3.org/2002/07/owl#equivalentClass"
OWL_EQUIVALENT_PROPERTY = "http://www.w3.org/2002/07/owl#equivalentProperty"
OWL_PROPERTY_CHAIN_AXIOM = "http://www.w3.org/2002/07/owl#propertyChainAxiom"


class MappingPredicateTokenError(ValueError):
    """A workbook predicate token is outside the supported vocabulary."""


_CURIE_TO_IRI = {
    "rdfs:subClassOf": RDFS_SUBCLASS_OF,
    "owl:equivalentClass": OWL_EQUIVALENT_CLASS,
    "rdfs:subPropertyOf": RDFS_SUBPROPERTY_OF,
    "owl:equivalentProperty": OWL_EQUIVALENT_PROPERTY,
    "owl:propertyChainAxiom": OWL_PROPERTY_CHAIN_AXIOM,
    "rdfs:domain": RDFS_DOMAIN,
    "rdfs:range": RDFS_RANGE,
}

_SUPPORTED_IRIS = frozenset(
    _CURIE_TO_IRI.values()
)


def normalize_mapping_predicate_token(
    token: str,
) -> str | None:
    """Return the canonical IRI for one supported workbook predicate token."""

    normalized = token.strip()

    if not normalized:
        return None

    if normalized in _SUPPORTED_IRIS:
        return normalized

    try:
        return _CURIE_TO_IRI[
            normalized
        ]
    except KeyError as exc:
        raise MappingPredicateTokenError(
            "unsupported mapping predicate token "
            f"{normalized!r}"
        ) from exc
