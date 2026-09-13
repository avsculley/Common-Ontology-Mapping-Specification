"""Declarative configuration primitives for COMS."""

from .model import (
    CatalogMapping,
    ExpressionProfile,
    FixedCountPolicy,
    HeaderBinding,
    PrefixBinding,
    ProductDefinition,
    ProductGraph,
    ProductText,
    ProjectConfig,
    PublicationProfile,
    ReleaseLayout,
    ValidationProfile,
    VocabularyProfile,
    VocabularyRole,
    WorkbookProfile,
)
from .validation import ConfigIssue, validate_project_config

__all__ = [
    "CatalogMapping",
    "ConfigIssue",
    "ExpressionProfile",
    "FixedCountPolicy",
    "HeaderBinding",
    "PrefixBinding",
    "ProductDefinition",
    "ProductGraph",
    "ProductText",
    "ProjectConfig",
    "PublicationProfile",
    "ReleaseLayout",
    "ValidationProfile",
    "VocabularyProfile",
    "VocabularyRole",
    "WorkbookProfile",
    "validate_project_config",
]
