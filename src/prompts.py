"""
prompts.py — Versioned prompt registry for the UK Motor Insurance IDP pipeline.

Loads prompt text from prompts.yaml so prompts can be updated, versioned, and
reviewed without touching Python source code.

Usage
-----
    registry = PromptRegistry()                         # uses active_version from YAML
    registry = PromptRegistry(version="v2")             # pin to a specific version
    registry = PromptRegistry(config_path="custom.yaml")

    system_prompt = registry.get(DocumentType.SCHEDULE)
    print(registry.active_version)   # → "v2" (the active_version in config/prompts.yaml)
    print(registry.available_versions)  # → ["v1", "v2"]
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import yaml

from schema import DocumentType

logger = logging.getLogger(__name__)

# Default path: <project_root>/config/prompts.yaml
# Resolved relative to this file's location (src/ → .. → config/)
_DEFAULT_CONFIG = Path(__file__).parent.parent / "config" / "prompts.yaml"

# Maps DocumentType enum values → YAML keys
_DOC_TYPE_TO_KEY: dict[DocumentType, str] = {
    DocumentType.SCHEDULE:          "Schedule",
    DocumentType.CERTIFICATE:       "Certificate",
    DocumentType.STATEMENT_OF_FACT: "StatementOfFact",
    DocumentType.POLICY_BOOKLET:    "PolicyBooklet",
    DocumentType.UNKNOWN:           "_generic",
}

_GENERIC_KEY = "_generic"


class PromptRegistry:
    """
    Loads versioned prompts from a YAML file and resolves them by DocumentType.

    Parameters
    ----------
    config_path : str | Path | None
        Path to the YAML file.  Defaults to ``src/prompts.yaml`` (sibling of
        this module).
    version : str | None
        Prompt version to activate (e.g. ``"v1"``, ``"v2"``).
        Defaults to the ``active_version`` key in the YAML file.
    """

    def __init__(
        self,
        config_path: Optional[str | Path] = None,
        version: Optional[str] = None,
    ) -> None:
        self._config_path = Path(config_path) if config_path else _DEFAULT_CONFIG
        self._raw = self._load_yaml()
        self._active_version = version or self._raw.get("active_version", "v1")
        self._prompts = self._resolve_version(self._active_version)

        logger.info(
            "PromptRegistry loaded: version=%s, path=%s",
            self._active_version,
            self._config_path,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def active_version(self) -> str:
        """The currently active prompt version string."""
        return self._active_version

    @property
    def available_versions(self) -> list[str]:
        """All version keys defined in the YAML file."""
        return list(self._raw.get("prompts", {}).keys())

    def get(self, doc_type: DocumentType) -> str:
        """
        Return the system prompt for a given DocumentType.

        Falls back to the ``_generic`` prompt if the specific key is missing.
        Raises ``KeyError`` if ``_generic`` is also absent (misconfigured YAML).
        """
        key = _DOC_TYPE_TO_KEY.get(doc_type, _GENERIC_KEY)
        prompt = self._prompts.get(key) or self._prompts.get(_GENERIC_KEY)
        if not prompt:
            raise KeyError(
                f"No prompt found for DocumentType '{doc_type.value}' in version "
                f"'{self._active_version}' of {self._config_path}. "
                f"Ensure '{key}' or '{_GENERIC_KEY}' is defined."
            )
        return prompt.strip()

    def reload(self) -> None:
        """
        Hot-reload prompts from disk without restarting the process.

        Useful in long-running services when prompts.yaml is updated in place.
        """
        self._raw = self._load_yaml()
        self._prompts = self._resolve_version(self._active_version)
        logger.info("PromptRegistry reloaded from %s", self._config_path)

    def switch_version(self, version: str) -> None:
        """
        Switch the active prompt version at runtime.

        Parameters
        ----------
        version : str
            Must be a key present under ``prompts:`` in the YAML file.
        """
        self._prompts = self._resolve_version(version)
        self._active_version = version
        logger.info("PromptRegistry switched to version '%s'", version)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_yaml(self) -> dict:
        if not self._config_path.exists():
            raise FileNotFoundError(
                f"Prompt configuration not found: {self._config_path}"
            )
        with self._config_path.open(encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}

    def _resolve_version(self, version: str) -> dict[str, str]:
        versions = self._raw.get("prompts", {})
        if version not in versions:
            available = list(versions.keys())
            raise ValueError(
                f"Prompt version '{version}' not found in {self._config_path}. "
                f"Available versions: {available}"
            )
        return versions[version]
