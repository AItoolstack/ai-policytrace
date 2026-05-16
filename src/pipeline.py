"""
pipeline.py — Shared PDF-routing and arbitration logic.

Both the CLI (main.py / DocumentPipeline) and the API (api.py / process_documents)
run the same extraction loop: route PDFs to Schedule/Certificate slots, call
the PolicyArbiter, and return the merged record plus any detected conflicts.

Extracting this logic here eliminates the duplication that previously existed
between those two entry-points and makes the behaviour easy to test in isolation.

Usage
-----
    from pipeline import run_extraction_pipeline

    golden, conflicts, corpora = run_extraction_pipeline(
        pdf_paths=pdf_paths,
        agent=agent,
        with_provenance=True,
    )
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from agents import ExtractionFailedError, InsuranceExtractionAgents
from arbiter import PolicyArbiter
from schema import ConflictEntry, DocumentType, UKMotorGoldenRecord

logger = logging.getLogger(__name__)


def run_extraction_pipeline(
    pdf_paths: list[Path],
    agent: InsuranceExtractionAgents,
    *,
    with_provenance: bool = False,
) -> tuple[UKMotorGoldenRecord, list[ConflictEntry], list[Any]]:
    """
    Route PDFs to Schedule/Certificate slots, arbitrate, and return the results.

    Parameters
    ----------
    pdf_paths : list[Path]
        Paths to the PDF documents to process.
    agent : InsuranceExtractionAgents
        Configured extraction agent (carries masker, debug_dir, prompts, etc.).
    with_provenance : bool
        When True, builds and returns ProvenanceCorpus objects for each PDF.
        Set to True when running via the API (Visual Audit UI needs geometry data).
        Set to False for the CLI path (faster, no corpus overhead).

    Returns
    -------
    tuple[UKMotorGoldenRecord, list[ConflictEntry], list[ProvenanceCorpus]]
        * golden_record   — the merged authoritative policy record
        * conflicts       — fields where Schedule and Certificate disagreed
        * corpora         — ProvenanceCorpus objects (empty list when with_provenance=False)

    Raises
    ------
    RuntimeError
        When neither a Schedule nor a Certificate could be extracted from any PDF.
    """
    schedule_record: UKMotorGoldenRecord | None = None
    schedule_filename = "unknown_schedule.pdf"
    certificate_record: UKMotorGoldenRecord | None = None
    certificate_filename = "unknown_certificate.pdf"
    corpora: list[Any] = []
    failed: list[str] = []

    for pdf_path in pdf_paths:
        try:
            if with_provenance:
                record, doc_type_str, corpus = agent.process_with_provenance(pdf_path)
                if corpus is not None and corpus.items:
                    corpora.append(corpus)
            else:
                record, doc_type_str = agent.process(pdf_path)

            logger.info("  ✓ %s → %s", pdf_path.name, doc_type_str)

            if doc_type_str == DocumentType.SCHEDULE.value and schedule_record is None:
                schedule_record = record
                schedule_filename = pdf_path.name
            elif doc_type_str == DocumentType.CERTIFICATE.value and certificate_record is None:
                certificate_record = record
                certificate_filename = pdf_path.name
            else:
                logger.info("  ~ %s (%s) — not used in merge", pdf_path.name, doc_type_str)

        except ExtractionFailedError as exc:
            logger.error("  ✗ Extraction failed for %s: %s", pdf_path.name, exc)
            failed.append(pdf_path.name)
        except Exception as exc:  # noqa: BLE001
            logger.error("  ✗ %s failed: %s", pdf_path.name, exc)
            failed.append(pdf_path.name)

    if failed:
        logger.warning("Skipped %d document(s): %s", len(failed), failed)

    if schedule_record is None and certificate_record is None:
        raise RuntimeError(
            "No Schedule or Certificate extracted. "
            "Check GROQ_API_KEY and that the PDFs are readable."
        )

    if schedule_record is None:
        logger.warning("No Schedule found — using empty record as fallback")
    if certificate_record is None:
        logger.warning("No Certificate found — using empty record as fallback")

    schedule_record = schedule_record or UKMotorGoldenRecord()
    certificate_record = certificate_record or UKMotorGoldenRecord()

    logger.info("Merging Schedule + Certificate via PolicyArbiter…")
    arbiter = PolicyArbiter()
    golden, conflicts = arbiter.merge_records(
        schedule_record, schedule_filename,
        certificate_record, certificate_filename,
    )

    if conflicts:
        logger.info(
            "Arbiter detected %d conflict(s): %s",
            len(conflicts),
            [c.field for c in conflicts],
        )

    return golden, conflicts, corpora
