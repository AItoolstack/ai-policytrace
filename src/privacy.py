"""
privacy.py — PII detection and masking via Microsoft Presidio.

Entities masked before any text is sent to the LLM:
  PERSON, PHONE_NUMBER, EMAIL_ADDRESS, UK_NHS, UK_NIN,
  CREDIT_CARD, IBAN_CODE, LOCATION, IP_ADDRESS, URL, DATE_TIME (opt-in)

Not masked: UK postcodes (Presidio has no UK postcode recogniser; LOCATION is
a named-entity model that catches place names, not postcodes) and often street
lines. Dates of birth are not masked unless DATE_TIME is enabled.

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
    "LOCATION",       # place names only; UK postcodes are NOT caught
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

        # Build NLP engine: spaCy en_core_web_lg if it is installed, otherwise
        # en_core_web_sm. Checking first matters: Presidio silently downloads a
        # missing model (400 MB for lg) instead of raising, so a try/except
        # fallback never triggers.
        nlp_config = {
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": "en", "model_name": _pick_spacy_model()}],
        }
        provider = NlpEngineProvider(nlp_configuration=nlp_config)
        nlp_engine = provider.create_engine()

        self._analyzer = AnalyzerEngine(nlp_engine=nlp_engine, supported_languages=[language])
        self._anonymizer = AnonymizerEngine()

        # Token assignments persist across mask() calls, so every document in a
        # pack masked by this instance gets the same token for the same value
        # ("Alex Morgan" is MASKED_PERSON_1 in the Schedule and the Certificate).
        # Without this, tokens were numbered per document and the arbiter's
        # driver matching paired the wrong people. Call reset() between packs.
        self._original_to_token: dict[tuple[str, str], str] = {}
        self._counters: dict[str, int] = {}

    def reset(self) -> None:
        """Forget token assignments, e.g. before masking an unrelated pack."""
        self._original_to_token.clear()
        self._counters.clear()

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

        token_map: dict[str, str] = {}

        # Sort by position so token numbering is left-to-right and deterministic
        results_sorted = sorted(results, key=lambda r: r.start)

        # Presidio's "replace" operator uses a fixed `new_value`, so tokens are
        # assigned here, keyed on (entity_type, normalised original) and shared
        # across calls on this instance.
        for r in results_sorted:
            original = text[r.start : r.end]
            key = _token_key(r.entity_type, original)
            token = self._original_to_token.get(key)
            if token is None:
                self._counters[r.entity_type] = self._counters.get(r.entity_type, 0) + 1
                token = f"{_TOKEN_PREFIX}{r.entity_type}_{self._counters[r.entity_type]}"
                self._original_to_token[key] = token
            token_map.setdefault(token, original)

        # Perform replacement manually (Presidio replace operator doesn't
        # support per-occurrence dynamic values in a single pass).
        masked_text = _replace_spans(text, results_sorted, self._original_to_token)
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


def _pick_spacy_model() -> str:
    """Return en_core_web_lg if installed, else en_core_web_sm."""
    try:
        import spacy.util

        if spacy.util.is_package("en_core_web_lg"):
            return "en_core_web_lg"
    except ImportError:
        pass
    return "en_core_web_sm"


def _token_key(entity_type: str, original: str) -> tuple[str, str]:
    """Token lookup key: same entity type, case and runs of whitespace ignored."""
    return entity_type, " ".join(original.split()).casefold()


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
        token = original_to_token.get(_token_key(r.entity_type, original), original)
        chars[r.start : r.end] = list(token)
    return "".join(chars)
