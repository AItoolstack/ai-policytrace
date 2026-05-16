"""
main.py — Agentic orchestrator for UK Motor Insurance IDP.

Usage
-----
    # Process all PDFs in a folder and print the Golden Record:
    python src/main.py --input ./docs --output ./output/golden_record.json

    # Verbose logging:
    python src/main.py --input ./docs --output ./output/golden_record.json --log-level DEBUG

Environment
-----------
    GROQ_API_KEY   Required. Your Groq API key.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

from agents import InsuranceExtractionAgents
from arbiter import PolicyArbiter
from pipeline import run_extraction_pipeline
from privacy import PIIMasker
from schema import DocumentType, UKMotorGoldenRecord
from settings import settings

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logger = logging.getLogger("pipeline")


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


class DocumentPipeline:
    """
    End-to-end agentic pipeline.

    Steps
    -----
    1. Scan *input_dir* for PDF files.
    2. For each PDF: mask PII → classify → extract with specialist agent.
    3. Pass all extractions to PolicyArbiter.
    4. Persist GoldenRecord JSON (with citations and conflict log) to *output_path*.
    """

    # Document-type priority for display ordering (matches arbiter priority)
    _DOC_ORDER = [
        DocumentType.SCHEDULE,
        DocumentType.CERTIFICATE,
        DocumentType.STATEMENT_OF_FACT,
        DocumentType.POLICY_BOOKLET,
        DocumentType.UNKNOWN,
    ]

    def __init__(
        self,
        input_dir: str | Path,
        output_path: str | Path = settings.pipeline.output_path,
        mask_dates: bool = settings.pii.mask_dates,
    ) -> None:
        self.input_dir = Path(input_dir)
        self.output_path = Path(output_path)

        # Create a timestamped debug run directory once per pipeline instance
        run_ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.debug_dir: Path | None = None
        if settings.debug.enabled:
            self.debug_dir = Path(settings.debug.output_dir) / f"run_{run_ts}"
            self.debug_dir.mkdir(parents=True, exist_ok=True)
            logger.info("Debug artifacts → %s", self.debug_dir)

        self._masker = PIIMasker(mask_dates=mask_dates)
        self._agent = InsuranceExtractionAgents(masker=self._masker, debug_dir=self.debug_dir)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> UKMotorGoldenRecord:
        """Execute the full pipeline and return the UKMotorGoldenRecord."""
        pdfs = self._discover_pdfs()
        if not pdfs:
            raise FileNotFoundError(
                f"No PDF files found in '{self.input_dir}'. "
                "Ensure the folder contains at least one .pdf file."
            )

        logger.info("Found %d PDF(s): %s", len(pdfs), [p.name for p in pdfs])

        # ── Stages 1 + 2: Extract + Arbitrate (shared logic via pipeline.py) ──
        golden, conflicts, _ = run_extraction_pipeline(
            pdf_paths=pdfs,
            agent=self._agent,
            with_provenance=False,
        )

        # ── Stage 3: Persist ──────────────────────────────────────────────
        self._save(golden)
        logger.info("Golden Record saved → %s", self.output_path)

        if conflicts and self.debug_dir:
            import json as _json
            (self.debug_dir / "conflicts.json").write_text(
                _json.dumps([c.model_dump() for c in conflicts], indent=2),
                encoding="utf-8",
            )
            logger.info(
                "Arbiter conflicts (%d) written → %s/conflicts.json",
                len(conflicts), self.debug_dir,
            )

        return golden

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _discover_pdfs(self) -> list[Path]:
        """Return PDF files sorted by document-type priority (best-effort)."""
        if not self.input_dir.is_dir():
            raise NotADirectoryError(f"'{self.input_dir}' is not a directory.")
        return sorted(self.input_dir.glob("*.pdf"), key=lambda p: p.name)

    def _save(self, golden: UKMotorGoldenRecord) -> None:
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.output_path.write_text(golden.model_dump_json(indent=2, exclude_none=True), encoding="utf-8")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Agentic UK Motor Insurance IDP Pipeline",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--input", "-i",
        required=True,
        help="Folder containing input PDF documents.",
    )
    parser.add_argument(
        "--output", "-o",
        default=settings.pipeline.output_path,
        help="Output path for the Golden Record JSON.",
    )
    parser.add_argument(
        "--mask-dates",
        action="store_true",
        default=False,
        help="Also redact DATE_TIME entities during PII masking.",
    )
    parser.add_argument(
        "--log-level",
        default=settings.pipeline.log_level,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    # ── Logging setup: console + optional file handler ─────────────────────
    log_format = "%(asctime)s [%(levelname)s] %(name)s — %(message)s"
    logging.basicConfig(
        level=args.log_level,
        format=log_format,
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )
    if settings.debug.enabled:
        run_ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        log_dir = Path(settings.debug.output_dir) / f"run_{run_ts}"
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_dir / "pipeline.log", encoding="utf-8")
        file_handler.setLevel(args.log_level)
        file_handler.setFormatter(logging.Formatter(log_format, datefmt="%H:%M:%S"))
        logging.getLogger().addHandler(file_handler)
        logger.info("Log file: %s", log_dir / "pipeline.log")

    pipeline = DocumentPipeline(
        input_dir=args.input,
        output_path=args.output,
        mask_dates=args.mask_dates,
    )

    golden = pipeline.run()

    # Print a compact summary to stdout
    hdr = golden.policy_header
    veh = golden.vehicle_details
    cov = golden.cover_and_excesses
    drivers = golden.driver_details or []
    print("\n" + "=" * 60)
    print("  GOLDEN RECORD SUMMARY")
    print("=" * 60)
    print(f"  Policy #      : {hdr.policy_number if hdr else 'N/A'}")
    print(f"  Insurer       : {hdr.insurer if hdr else 'N/A'}")
    print(f"  VRM           : {veh.vrm if veh else 'N/A'}")
    print(f"  Vehicle       : {(veh.make + ' ' + veh.model) if veh and veh.make else 'N/A'}")
    print(f"  Cover         : {cov.cover_type if cov else 'N/A'}")
    print(f"  Class of use  : {cov.class_of_use if cov else 'N/A'}")
    print(f"  Drivers       : {len(drivers)}")
    print("=" * 60)
    print(f"\nFull JSON written to: {args.output}\n")


if __name__ == "__main__":
    main()
