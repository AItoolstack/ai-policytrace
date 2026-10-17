"""
settings.py — Pipeline configuration loader.

Merges values from config/settings.yaml with environment variable overrides.
Also calls load_dotenv() so importing this module anywhere in the pipeline
is sufficient to activate .env — no separate setup needed.

Precedence (highest → lowest)
──────────────────────────────
  1. Environment variables (GROQ_MODEL, etc.)
  2. config/settings.yaml
  3. Pydantic model field defaults (safety net)

Usage
-----
    from settings import settings

    model   = settings.llm.model          # respects GROQ_MODEL env var
    retries = settings.llm.max_retries
    thresh  = settings.pii.score_threshold
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Load .env file before anything else reads os.environ
load_dotenv()

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "config" / "settings.yaml"

# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------

_DEFAULT_ENTITIES = [
    "PERSON", "PHONE_NUMBER", "EMAIL_ADDRESS",
    "UK_NHS", "UK_NIN", "CREDIT_CARD", "IBAN_CODE",
    "LOCATION", "IP_ADDRESS", "URL",
]


class LLMSettings(BaseModel):
    model: str = "openai/gpt-oss-120b"
    classifier_model: str = "openai/gpt-oss-20b"
    max_retries: int = 2


class PIISettings(BaseModel):
    score_threshold: float = 0.5
    mask_dates: bool = False
    language: str = "en"
    entities: list[str] = Field(default_factory=lambda: list(_DEFAULT_ENTITIES))


class PipelineSettings(BaseModel):
    output_path: str = "./output/golden_record.json"
    log_level: str = "INFO"
    session_ttl_days: int = 30  # sessions older than this are removed on API startup (0 = disabled)


class DebugSettings(BaseModel):
    enabled: bool = True
    output_dir: str = "./output/debug"
    save_markdown: bool = True
    save_masked_markdown: bool = True
    save_extraction_json: bool = True
    save_metrics: bool = True


class DoclingSettings(BaseModel):
    do_ocr: bool = False
    do_table_structure: bool = False
    # Per-document-type page caps (None = no limit)
    max_pages: dict[str, int | None] = Field(
        default_factory=lambda: {
            "Schedule": None,
            "Certificate": None,
            "StatementOfFact": None,
            "PolicyBooklet": 20,
            "Unknown": 30,
        }
    )


class Settings(BaseModel):
    llm: LLMSettings = Field(default_factory=LLMSettings)
    pii: PIISettings = Field(default_factory=PIISettings)
    pipeline: PipelineSettings = Field(default_factory=PipelineSettings)
    debug: DebugSettings = Field(default_factory=DebugSettings)
    docling: DoclingSettings = Field(default_factory=DoclingSettings)

    @classmethod
    def load(cls, config_path: Optional[str | Path] = None) -> "Settings":
        """
        Load settings from YAML, then apply environment variable overrides.

        Parameters
        ----------
        config_path : str | Path | None
            Path to a settings YAML file.  Defaults to config/settings.yaml.
        """
        path = Path(config_path) if config_path else _DEFAULT_CONFIG_PATH
        data: dict = {}

        if path.exists():
            with path.open(encoding="utf-8") as fh:
                data = yaml.safe_load(fh) or {}
            logger.debug("Settings loaded from %s", path)
        else:
            logger.warning(
                "Settings file not found at %s — using defaults.", path
            )

        instance = cls.model_validate(data)

        # ── Environment variable overrides ─────────────────────────────────
        # GROQ_MODEL wins over both settings.yaml and the Pydantic default.
        if groq_model := os.environ.get("GROQ_MODEL"):
            instance.llm.model = groq_model
            logger.debug("LLM model overridden by GROQ_MODEL env var: %s", groq_model)

        if classifier_model := os.environ.get("GROQ_CLASSIFIER_MODEL"):
            instance.llm.classifier_model = classifier_model
            logger.debug("Classifier model overridden by GROQ_CLASSIFIER_MODEL env var: %s", classifier_model)

        return instance


# ---------------------------------------------------------------------------
# Module-level singleton — import this everywhere
# ---------------------------------------------------------------------------

settings = Settings.load()
