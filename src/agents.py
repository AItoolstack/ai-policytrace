"""
agents.py — Specialist document extraction agents for UK Motor Insurance.

Architecture
────────────
  PDF path
    → docling  (PDF → Markdown)
    → PIIMasker.mask()
    → InsuranceExtractionAgents.classify_document()  [LLM: llama-3.1-8b-instant]
    → extract_schedule() | extract_certificate()     [LLM: llama-4-scout-17b]
    → UKMotorGoldenRecord (with source_document provenance)
"""
from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

import instructor
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from groq import Groq
from pydantic import ValidationError

from privacy import PIIMasker
from prompts import PromptRegistry
from schema import DocumentType, SourceMetadata, UKMotorGoldenRecord
from settings import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Groq clients — extraction (instructor-wrapped) + classifier (raw Groq)
# ---------------------------------------------------------------------------


def _build_extraction_client() -> instructor.Instructor:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GROQ_API_KEY environment variable is not set. "
            "Export it before running the pipeline."
        )
    return instructor.from_groq(Groq(api_key=api_key), mode=instructor.Mode.JSON)


def _build_groq_client() -> Groq:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GROQ_API_KEY environment variable is not set. "
            "Export it before running the pipeline."
        )
    return Groq(api_key=api_key)


# Models resolved at import time from settings.yaml / env vars
_EXTRACTION_MODEL: str = settings.llm.model
_CLASSIFIER_MODEL: str = settings.llm.classifier_model


def _build_docling_converter() -> DocumentConverter:
    """Build a DocumentConverter configured from settings.docling."""
    opts = PdfPipelineOptions()
    opts.do_ocr = settings.docling.do_ocr
    opts.do_table_structure = settings.docling.do_table_structure
    return DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)}
    )

# ---------------------------------------------------------------------------
# Document type classifier (keyword heuristic — fast, zero API calls)
# ---------------------------------------------------------------------------

_CLASSIFICATION_KEYWORDS: dict[DocumentType, list[str]] = {
    DocumentType.SCHEDULE: [
        # Phrases that only appear in a Schedule, not in a Certificate
        "policy schedule",
        "schedule of insurance",
        "schedule number",
        "premium payable",
        "compulsory excess",
        "voluntary excess",
        "no claims bonus",
        "ncb",
        "windscreen excess",
    ],
    DocumentType.CERTIFICATE: [
        # Phrases that are definitive for a Certificate document
        "certificate of motor insurance",
        "motor insurance certificate",
        "certificate number",
        "persons entitled to drive",
        "class of use",
        "road traffic act",
        "this is to certify",
    ],
    DocumentType.STATEMENT_OF_FACT: [
        "statement of fact",
        "statement of insurance",
        "proposal form",
        "claims history",
        "motoring convictions",
        "annual mileage",
    ],
    DocumentType.POLICY_BOOKLET: [
        "policy booklet",
        "policy wording",
        "terms and conditions",
        "what is covered",
        "general conditions",
        "complaints procedure",
    ],
}


def _keyword_classify(text: str) -> str:
    """Keyword heuristic fallback classifier. Returns DocumentType.value string."""
    lower = text.lower()
    scores: dict[DocumentType, int] = {dt: 0 for dt in _CLASSIFICATION_KEYWORDS}

    for doc_type, keywords in _CLASSIFICATION_KEYWORDS.items():
        for kw in keywords:
            if kw in lower:
                scores[doc_type] += 1

    best_type, best_score = max(scores.items(), key=lambda kv: kv[1])
    return best_type.value if best_score > 0 else DocumentType.UNKNOWN.value


def _str_to_doc_type(s: str) -> DocumentType:
    """Convert a string to DocumentType, falling back to UNKNOWN."""
    try:
        return DocumentType(s)
    except ValueError:
        return DocumentType.UNKNOWN


# ---------------------------------------------------------------------------
# Extraction failure sentinel
# ---------------------------------------------------------------------------


class ExtractionFailedError(RuntimeError):
    """
    Raised when the LLM fails to produce a valid UKMotorGoldenRecord after
    exhausting all retries.  Callers should treat the document as failed and
    skip it rather than propagating an empty record silently.
    """


# ---------------------------------------------------------------------------
# InsuranceExtractionAgents
# ---------------------------------------------------------------------------


class InsuranceExtractionAgents:
    """
    Specialist extraction agents for UK Motor Insurance documents.

    Uses two LLM models:
    - llama-3.1-8b-instant     — fast document type classification
    - llama-4-scout-17b-16e    — deep structured extraction (Schedule / Certificate)

    Parameters
    ----------
    masker : PIIMasker | None
    max_retries : int
    prompt_registry : PromptRegistry | None
    debug_dir : Path | None
    """

    def __init__(
        self,
        masker: PIIMasker | None = None,
        max_retries: int = settings.llm.max_retries,
        prompt_registry: PromptRegistry | None = None,
        debug_dir: Path | None = None,
    ) -> None:
        self._client = _build_extraction_client()
        self._groq = _build_groq_client()
        self._masker = masker or PIIMasker()
        self._max_retries = max_retries
        self._prompts = prompt_registry or PromptRegistry()
        self._converter = _build_docling_converter()
        self._debug_dir = debug_dir

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def classify_document(self, markdown_text: str) -> str:
        """
        Use llama-3.1-8b-instant to classify the document type.

        The LLM is the primary classifier.  If it fails or returns an invalid
        label, the keyword heuristic is used as a fallback.  A discrepancy
        between the two is logged as a warning to flag low-confidence cases.

        Returns one of: "Schedule", "Certificate", "StatementOfFact",
        "PolicyBooklet", "Unknown".
        """
        keyword_result = _keyword_classify(markdown_text)

        system_prompt = (
            "You are a UK motor insurance document classifier.\n"
            "Given the document text, respond with EXACTLY one word from:\n"
            "Schedule | Certificate | StatementOfFact | PolicyBooklet | Unknown\n\n"
            "- Schedule: Policy Schedule \u2014 excess figures, premium, NCB, "
            "vehicle details, driver ages/DOBs.\n"
            "- Certificate: Certificate of Motor Insurance \u2014 Road Traffic Act, "
            "'persons entitled to drive', 'class of use'.\n"
            "- StatementOfFact: Statement of Fact / Proposal \u2014 claims history, "
            "convictions, annual mileage.\n"
            "- PolicyBooklet: Policy Booklet / Wording \u2014 terms and conditions, "
            "'what is covered', complaints.\n"
            "- Unknown: Cannot determine.\n\n"
            "Respond with ONLY the single classification word. No punctuation."
        )
        try:
            response = self._groq.chat.completions.create(
                model=_CLASSIFIER_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": "Classify this document:\n\n" + markdown_text[:4000],
                    },
                ],
                max_tokens=10,
                temperature=0,
            )
            llm_result = response.choices[0].message.content.strip().split()[0]
            valid = {"Schedule", "Certificate", "StatementOfFact", "PolicyBooklet", "Unknown"}
            if llm_result in valid:
                if llm_result != keyword_result:
                    logger.warning(
                        "Classifier discrepancy: LLM=%s, keyword=%s "
                        "(using LLM result — verify document type)",
                        llm_result, keyword_result,
                    )
                else:
                    logger.debug("Classifier agreement: LLM=%s \u2713", llm_result)
                return llm_result
            logger.warning(
                "LLM classifier returned '%s' \u2014 falling back to keyword heuristic", llm_result
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "LLM classifier failed (%s) \u2014 falling back to keyword heuristic", exc
            )
        return keyword_result

    def extract_schedule(self, markdown_text: str, filename: str) -> UKMotorGoldenRecord:
        """
        Extract all financial, vehicle, and driver risk data from a Policy Schedule.

        Instructs the LLM to:
        - Compute total_accidental_damage = standard_compulsory + voluntary
        - Extract driver DOBs and distinguish Full UK vs UK Provisional licence types
        - Separate fire excess from theft excess (they can differ)
        - Extract own_repairer_additional_excess if present
        - Extract premium breakdown and optional extras (float if purchased,
          "Not Selected" if not)
        """
        return self._extract(
            markdown_text,
            filename,
            DocumentType.SCHEDULE,
            self._prompts.get(DocumentType.SCHEDULE),
        )

    def extract_certificate(self, markdown_text: str, filename: str) -> UKMotorGoldenRecord:
        """
        Extract legal permissions from a Certificate of Motor Insurance.

        Instructs the LLM to:
        - Extract the exact "Limitations as to use" / class_of_use clause verbatim
        - Extract the policy_number for cross-reference
        - Record driving_other_cars entitlement (true/false)
        - Leave all financial fields (excess, premium, NCB) as null
        """
        return self._extract(
            markdown_text,
            filename,
            DocumentType.CERTIFICATE,
            self._prompts.get(DocumentType.CERTIFICATE),
        )

    def process(self, pdf_path: str | Path) -> tuple[UKMotorGoldenRecord, str]:
        """
        Full pipeline for one PDF: PDF → Markdown → PII mask → classify → extract.

        Returns
        -------
        tuple[UKMotorGoldenRecord, str]
            The extracted record and the document type string (e.g. "Schedule").

        Raises
        ------
        ExtractionFailedError
            When the LLM fails to extract a valid record after all retries.
        """
        record, doc_type_str, _ = self._process_internal(Path(pdf_path), build_corpus=False)
        return record, doc_type_str

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _process_internal(
        self,
        pdf_path: Path,
        build_corpus: bool,
    ) -> tuple[UKMotorGoldenRecord, str, Any]:
        """
        Unified core pipeline: PDF → Markdown → PII mask → classify → extract,
        optionally building a ProvenanceCorpus from the raw Docling IR.

        Parameters
        ----------
        pdf_path : Path
        build_corpus : bool
            When True, builds a ProvenanceCorpus before PII masking so the
            original text is available for fuzzy matching.

        Returns
        -------
        tuple[UKMotorGoldenRecord, str, ProvenanceCorpus | None]
            (record, doc_type_str, corpus_or_None)

        Raises
        ------
        ExtractionFailedError
            Propagated from _extract() when the LLM fails after all retries.
        """
        from provenance import ProvenanceCorpus  # local import — avoids circular dep

        logger.info("Processing%s: %s", " (with provenance)" if build_corpus else "", pdf_path.name)

        # Pre-classify from filename for page-cap selection (no API call)
        pre_type_str = _keyword_classify(pdf_path.stem)
        pre_doc_type = _str_to_doc_type(pre_type_str)
        logger.debug("  Pre-classified from filename: %s", pre_type_str)

        # PDF → Markdown + raw DoclingDocument
        markdown, raw_doc = self._pdf_to_markdown_and_doc(pdf_path, pre_doc_type)

        # Build corpus from original text BEFORE masking (critical for accurate fuzzy match)
        corpus: Any = None
        if build_corpus:
            corpus = ProvenanceCorpus(source_filename=pdf_path.name, doc_type=pre_type_str)
            corpus.add_from_docling(raw_doc, pdf_path.name)
            logger.debug("  Provenance corpus: %d items", len(corpus.items))

        if self._debug_dir and settings.debug.save_markdown:
            _write_debug(self._debug_dir, f"{pdf_path.name}.md", markdown)

        # PII mask
        masked_markdown, _token_map = self._masker.mask(markdown)
        if self._debug_dir and settings.debug.save_masked_markdown:
            _write_debug(self._debug_dir, f"{pdf_path.name}.masked.md", masked_markdown)

        # Classify
        t0 = time.monotonic()
        doc_type_str = self.classify_document(masked_markdown)
        logger.info("  Classified as: %s", doc_type_str)

        # Route to specialist extractor
        if doc_type_str == "Schedule":
            record = self.extract_schedule(masked_markdown, pdf_path.name)
        elif doc_type_str == "Certificate":
            record = self.extract_certificate(masked_markdown, pdf_path.name)
        else:
            logger.info("  Non-primary type '%s' — running generic extraction", doc_type_str)
            record = self._extract(
                masked_markdown,
                pdf_path.name,
                _str_to_doc_type(doc_type_str),
                self._prompts.get(_str_to_doc_type(doc_type_str)),
            )

        elapsed = round(time.monotonic() - t0, 3)

        record.source_document = SourceMetadata(
            document_type=_str_to_doc_type(doc_type_str),
            filename=pdf_path.name,
        )

        if self._debug_dir and settings.debug.save_extraction_json:
            _write_debug(
                self._debug_dir,
                f"{pdf_path.name}.extraction.json",
                record.model_dump_json(indent=2),
            )
            fc = getattr(record, "field_citations", None) or {}
            logger.info("  field_citations populated by LLM: %d entries", len(fc))
            if fc:
                import json as _json
                _write_debug(
                    self._debug_dir,
                    f"{pdf_path.name}.field_citations.json",
                    _json.dumps(fc, indent=2, ensure_ascii=False),
                )

        if self._debug_dir and settings.debug.save_metrics:
            metrics: dict = {
                "filename": pdf_path.name,
                "doc_type": doc_type_str,
                "extraction_model": _EXTRACTION_MODEL,
                "classifier_model": _CLASSIFIER_MODEL,
                "response_time_seconds": elapsed,
            }
            if corpus is not None:
                metrics["corpus_items"] = len(corpus.items)
            _append_metrics(self._debug_dir, metrics)

        return record, doc_type_str, corpus

    def _pdf_to_markdown(
        self, pdf_path: Path, doc_type: DocumentType = DocumentType.UNKNOWN
    ) -> str:
        """Convert a PDF to Markdown using docling, respecting per-doc-type page caps."""
        markdown, _ = self._pdf_to_markdown_and_doc(pdf_path, doc_type)
        return markdown

    def _pdf_to_markdown_and_doc(
        self, pdf_path: Path, doc_type: DocumentType = DocumentType.UNKNOWN
    ) -> tuple[str, Any]:
        """Convert PDF to Markdown and also return the raw DoclingDocument for provenance."""
        # Apply page cap during conversion (not just in Markdown export) to prevent
        # Docling's layout model from running out of memory on large PDFs (Policy Booklet).
        max_pg = settings.docling.max_pages.get(doc_type.value)
        convert_kwargs: dict[str, Any] = {}
        if max_pg is not None:
            convert_kwargs["max_num_pages"] = max_pg

        result = self._converter.convert(str(pdf_path), **convert_kwargs)
        doc = result.document
        markdown = doc.export_to_markdown()

        if max_pg is not None:
            separator = "\n---\n"
            parts = markdown.split(separator)
            if len(parts) > max_pg:
                logger.info(
                    "  Page cap applied: %s capped at %d/%d pages",
                    pdf_path.name, max_pg, len(parts),
                )
                markdown = separator.join(parts[:max_pg])

        return markdown, doc

    def process_with_provenance(
        self, pdf_path: str | Path
    ) -> tuple[UKMotorGoldenRecord, str, Any]:
        """
        Like process() but also returns a ProvenanceCorpus built from the Docling IR.

        The corpus is constructed *before* PII masking so that the original text
        strings (not masked tokens) are available for fuzzy matching.

        Returns
        -------
        tuple[UKMotorGoldenRecord, str, ProvenanceCorpus]
            (record, doc_type_str, corpus)

        Raises
        ------
        ExtractionFailedError
            When the LLM fails to extract a valid record after all retries.
        """
        return self._process_internal(Path(pdf_path), build_corpus=True)  # type: ignore[return-value]

    def _extract(
        self,
        text: str,
        filename: str,
        doc_type: DocumentType,
        system_prompt: str,
    ) -> UKMotorGoldenRecord:
        """Call Groq via instructor to extract a UKMotorGoldenRecord."""
        user_message = (
            "Extract all motor insurance data from the following document text. "
            "Return a JSON object that strictly conforms to the UKMotorGoldenRecord schema.\n\n"
            f"--- DOCUMENT TEXT ---\n{text}\n--- END ---"
        )
        try:
            record: UKMotorGoldenRecord = self._client.chat.completions.create(
                model=_EXTRACTION_MODEL,
                response_model=UKMotorGoldenRecord,
                max_retries=self._max_retries,
                messages=[
                    {"role": "system", "content": system_prompt.strip()},
                    {"role": "user", "content": user_message},
                ],
            )
        except (ValidationError, Exception) as exc:
            raise ExtractionFailedError(
                f"Extraction failed for {doc_type.value!r} document '{filename}' "
                f"after {self._max_retries} retries: {exc}"
            ) from exc
        return record


# ---------------------------------------------------------------------------
# Debug helpers (module-level so they can be unit-tested independently)
# ---------------------------------------------------------------------------


def _write_debug(debug_dir: Path, filename: str, content: str) -> None:
    """Write a debug artifact to disk, silently skipping on any I/O error."""
    try:
        (debug_dir / filename).write_text(content, encoding="utf-8")
        logger.debug("Debug artifact saved: %s", filename)
    except OSError as exc:
        logger.warning("Could not write debug artifact %s: %s", filename, exc)


def _append_metrics(debug_dir: Path, metrics: dict) -> None:
    """Append a metrics dict as a JSONL line to extraction_metrics.jsonl."""
    try:
        with (debug_dir / "extraction_metrics.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(metrics) + "\n")
    except OSError as exc:
        logger.warning("Could not write metrics: %s", exc)
