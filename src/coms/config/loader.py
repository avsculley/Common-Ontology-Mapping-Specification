"""TOML file loading for COMS project configuration.

This module owns configuration-file I/O only. It does not resolve project
paths, inspect referenced files, validate project semantics, or execute
runtime policy.
"""

from __future__ import annotations

from os import PathLike
from pathlib import Path
import tomllib

from .model import ProjectConfig
from .schema import parse_project_config


class ConfigLoadError(ValueError):
    """Raised when a configuration file cannot be decoded as TOML."""

    def __init__(
        self,
        *,
        code: str,
        path: str,
        message: str,
    ) -> None:
        self.code = code
        self.path = path
        self.message = message

        super().__init__(
            f"{path}: {code}: {message}"
        )


def load_project_config(
    path: str | PathLike[str],
) -> ProjectConfig:
    """Load one TOML file and parse it as COMS configuration.

    Schema errors raised by ``parse_project_config`` are intentionally not
    wrapped. Semantic validation is intentionally not invoked here.
    """

    source = Path(path)

    try:
        with source.open("rb") as stream:
            data = tomllib.load(stream)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigLoadError(
            code="invalid_toml",
            path=str(source),
            message=str(exc),
        ) from exc
    except UnicodeDecodeError as exc:
        raise ConfigLoadError(
            code="invalid_encoding",
            path=str(source),
            message=str(exc),
        ) from exc
    except OSError as exc:
        raise ConfigLoadError(
            code="read_error",
            path=str(source),
            message=(
                exc.strerror
                if exc.strerror is not None
                else str(exc)
            ),
        ) from exc

    return parse_project_config(data)
