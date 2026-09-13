"""Declarative configuration primitives for COMS."""

from .model import (
    CatalogMapping,
    ExpressionProfile,
    FixedCountPolicy,
    HeaderBinding,
    PrefixBinding,
    ProductDefinition,
    ProductImport,
    ProductImportFormalTarget,
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
from .loader import ConfigLoadError, load_project_config
from .schema import (
    SUPPORTED_CONFIGURATION_SCHEMA_VERSION,
    ConfigSchemaError,
    ConfigSchemaIssue,
    parse_project_config,
)
from .validation import ConfigIssue, validate_project_config

__all__ = [
    "CatalogMapping",
    "ConfigIssue",
    "ConfigSchemaError",
    "ConfigSchemaIssue",
    "ExpressionProfile",
    "FixedCountPolicy",
    "HeaderBinding",
    "PrefixBinding",
    "ProductDefinition",
    "ProductImport",
    "ProductImportFormalTarget",
    "ProductGraph",
    "ProductText",
    "ProjectConfig",
    "PublicationProfile",
    "ReleaseLayout",
    "SUPPORTED_CONFIGURATION_SCHEMA_VERSION",
    "ValidationProfile",
    "VocabularyProfile",
    "VocabularyRole",
    "WorkbookProfile",
    "validate_project_config",
    "ConfigLoadError",
    "load_project_config",
    "parse_project_config",

]
