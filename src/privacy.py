"""
privacy.py — PII detection and masking via Microsoft Presidio.

Entities masked before any text is sent to the LLM:
  PERSON, PHONE_NUMBER, EMAIL_ADDRESS, UK_NHS, UK_NIN,
  CREDIT_CARD, IBAN_CODE, DATE_TIME (opt-in), LOCATION

Usage
-----
    masker = PIIMasker()
    clean_text, mapping = masker.mask(raw_markdown)
    # ... call LLM with clean_text ...
    # If you ever need to restore originals:
    restored = masker.restore(llm_output, mapping)
"""
from __future__ import annotations

import re
from typing import Optional

from presidio_analyzer import AnalyzerEngine, RecognizerResult
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

from settings import settings


# ---------------------------------------------------------------------------
# Default entity list (tuned for UK motor insurance documents)
# ---------------------------------------------------------------------------

UK_MOTOR_ENTITIES: list[str] = [
    "PERSON",
    "PHONE_NUMBER",
    "EMAIL_ADDRESS",
    "UK_NHS",
    "UK_NIN",         # National Insurance Number
    "CREDIT_CARD",
    "IBAN_CODE",
    "LOCATION",       # postcodes / addresses
    "IP_ADDRESS",
    "URL",
]

# Sentinel prefix used for replacement tokens so we can detect them reliably
_TOKEN_PREFIX = "MASKED_"


class PIIMasker:
    """
    Stateless masker: call `mask()` to redact PII in a text string.

    Parameters
    ----------
    entities : list[str]
        Presidio entity types to redact.  Defaults to UK_MOTOR_ENTITIES.
    language : str
        ISO 639-1 language code passed to the Presidio analyzer.
    mask_dates : bool
        When True, DATE_TIME entities are also redacted.  Default False
        because insurance documents are date-heavy and stripping them
        would break structured extraction.
    score_threshold : float
        Minimum confidence score (0-1) for a detected entity to be masked.
    """

    def __init__(
        self,
        entities: Optional[list[str]] = None,
        language: str = settings.pii.language,
        mask_dates: bool = settings.pii.mask_dates,
        score_threshold: float = settings.pii.score_threshold,
    ) -> None:
        self._entities = list(entities or settings.pii.entities)
        if mask_dates and "DATE_TIME" not in self._entities:
            self._entities.append("DATE_TIME")

        self._language = language
        self._score_threshold = score_threshold

        # Build NLP engine (spaCy en_core_web_lg preferred; falls back to sm)
        nlp_config = {
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": "en", "model_name": "en_core_web_lg"}],
        }
        try:
            provider = NlpEngineProvider(nlp_configuration=nlp_config)
            nlp_engine = provider.create_engine()
        except OSError:
            # Fall back to the small model if lg is not installed
            nlp_config["models"][0]["model_name"] = "en_core_web_sm"
            provider = NlpEngineProvider(nlp_configuration=nlp_config)
            nlp_engine = provider.create_engine()

        self._analyzer = AnalyzerEngine(nlp_engine=nlp_engine, supported_languages=[language])
        self._anonymizer = AnonymizerEngine()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def mask(self, text: str) -> tuple[str, dict[str, str]]:
        """
        Redact PII in *text* and return (masked_text, token_map).

        token_map maps placeholder tokens back to original values, allowing
        optional restoration after LLM processing.

        Example
        -------
        >>> masked, mapping = masker.mask("John Smith drives AB12 CDE")
        >>> masked
        'MASKED_PERSON_1 drives AB12 CDE'
        >>> mapping
        {'MASKED_PERSON_1': 'John Smith'}
        """
        results: list[RecognizerResult] = self._analyzer.analyze(
            text=text,
            entities=self._entities,
            language=self._language,
            score_threshold=self._score_threshold,
        )

        if not results:
            return text, {}

        # Build per-entity-type counters for unique token names
        counters: dict[str, int] = {}
        token_map: dict[str, str] = {}
        operators: dict[str, OperatorConfig] = {}

        # Sort by position so token numbering is left-to-right and deterministic
        results_sorted = sorted(results, key=lambda r: r.start)

        # We need custom lambda operators to generate named tokens.
        # Presidio's "replace" operator uses a fixed `new_value`; we work
        # around this by building a value map keyed on (entity_type, original).
        original_to_token: dict[tuple[str, str], str] = {}

        for r in results_sorted:
            original = text[r.start : r.end]
            key = (r.entity_type, original)
            if key not in original_to_token:
                counters[r.entity_type] = counters.get(r.entity_type, 0) + 1
                token = f"{_TOKEN_PREFIX}{r.entity_type}_{counters[r.entity_type]}"
                original_to_token[key] = token
                token_map[token] = original

        # Perform replacement manually (Presidio replace operator doesn't
        # support per-occurrence dynamic values in a single pass).
        masked_text = _replace_spans(text, results_sorted, original_to_token)
        return masked_text, token_map

    def restore(self, text: str, token_map: dict[str, str]) -> str:
        """
        Substitute masked tokens back to original PII values.

        This is provided for completeness / testing; in production the LLM
        output is kept masked and stored as-is for GDPR compliance.
        """
        for token, original in token_map.items():
            text = text.replace(token, original)
        return text


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _replace_spans(
    text: str,
    results: list[RecognizerResult],
    original_to_token: dict[tuple[str, str], str],
) -> str:
    """
    Replace PII spans in *text* with their corresponding tokens.
    Processes spans right-to-left to keep offset arithmetic valid.
    """
    chars = list(text)
    for r in sorted(results, key=lambda r: r.start, reverse=True):
        original = text[r.start : r.end]
        token = original_to_token.get((r.entity_type, original), original)
        chars[r.start : r.end] = list(token)
    return "".join(chars)
