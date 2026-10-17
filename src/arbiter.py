"""
arbiter.py — Hierarchy of Truth merge for UK Motor Insurance.

The PolicyArbiter takes one Schedule extraction and one Certificate extraction
and produces a single authoritative UKMotorGoldenRecord.

    Document         Authoritative for
    ──────────────── ──────────────────────────────────────────────────
    Schedule         vehicle_details, excess_breakdown, financial_summary,
                     driver DOB / occupation / license_type, NCB, cover_type
    Certificate      class_of_use, driving_other_cars
"""
from __future__ import annotations

import logging
from typing import Optional

from schema import (
    ConflictEntry,
    CoverAndExcesses,
    Driver,
    ExcessBreakdown,
    NoClaimsDiscount,
    PeriodOfCover,
    PolicyHeader,
    UKMotorGoldenRecord,
)

logger = logging.getLogger(__name__)

# Minimum rapidfuzz token_sort_ratio to consider two driver names a match.
_DRIVER_NAME_MATCH_THRESHOLD = 85


# ---------------------------------------------------------------------------
# PolicyArbiter
# ---------------------------------------------------------------------------


class PolicyArbiter:
    """
    Merges a Schedule extraction and a Certificate extraction into one
    authoritative UKMotorGoldenRecord using the Hierarchy of Truth.

    Usage
    -----
    >>> arbiter = PolicyArbiter()
    >>> golden, conflicts = arbiter.merge_records(
    ...     schedule_record, "Schedule of Insurance (1).pdf",
    ...     certificate_record, "Certificate of Motor Insurance.pdf",
    ... )
    """

    def merge_records(
        self,
        schedule_record: UKMotorGoldenRecord,
        schedule_filename: str,
        certificate_record: UKMotorGoldenRecord,
        certificate_filename: str,
    ) -> tuple[UKMotorGoldenRecord, list[ConflictEntry]]:
        """
        Merge Schedule and Certificate extractions into one Golden Record.

        Schedule is master for: vehicle_details, excess_breakdown,
        financial_summary, driver DOB/occupation/license_type, NCB, cover_type.
        Certificate is master for: class_of_use, driving_other_cars.

        Returns
        -------
        tuple[UKMotorGoldenRecord, list[ConflictEntry]]
            (golden_record, list of fields where the two documents disagreed)
        """
        conflicts: list[ConflictEntry] = []
        merged = UKMotorGoldenRecord()

        # ── Policy header ───────────────────────────────────────────────────
        merged.policy_header = _merge_policy_header(schedule_record, certificate_record, conflicts)

        # ── Vehicle details: Schedule is authoritative ──────────────────────
        merged.vehicle_details = schedule_record.vehicle_details

        # ── Drivers: Schedule has DOB/occupation/licence ────────────────────
        merged.driver_details = _merge_drivers(schedule_record, certificate_record, conflicts)

        # ── Cover and excesses: hybrid ──────────────────────────────────────
        # class_of_use + driving_other_cars → Certificate
        # cover_type + NCB + excess_breakdown → Schedule
        merged.cover_and_excesses = _merge_cover_and_excesses(
            schedule_record, certificate_record, conflicts
        )

        # ── Financial summary: Schedule is authoritative ────────────────────
        merged.financial_summary = schedule_record.financial_summary

        # ── Additional risk data: Schedule is authoritative ─────────────────
        merged.additional_risk_data = schedule_record.additional_risk_data

        # ── Merge field_citations from both source records ──────────────────
        # Schedule wins on key conflicts (consistent with merge hierarchy).
        # Stored on the merged record for provenance matching; excluded from JSON output.
        sched_fc = dict(getattr(schedule_record, "field_citations", None) or {})
        cert_fc = dict(getattr(certificate_record, "field_citations", None) or {})
        merged_fc = {**cert_fc, **sched_fc}
        if merged_fc:
            merged.field_citations = merged_fc

        if conflicts:
            logger.info(
                "Merge conflicts (%d): %s",
                len(conflicts),
                [c.field for c in conflicts],
            )

        logger.info(
            "Merge complete: schedule='%s' + certificate='%s' — %d conflict(s)",
            schedule_filename, certificate_filename, len(conflicts),
        )
        return merged, conflicts


# ---------------------------------------------------------------------------
# Private merge helpers
# ---------------------------------------------------------------------------


def _first(*values):
    """Return the first non-None value, or None if all are None."""
    for v in values:
        if v is not None:
            return v
    return None


def _normalise(value) -> str:
    """Comparison key: case-insensitive, with runs of whitespace collapsed.

    PDF text extraction often leaves double spaces inside a value
    ("Motor  Insurance"), which is not a real disagreement.
    """
    return " ".join(str(value).split()).lower()


def _check_conflict(
    conflicts: list[ConflictEntry],
    field: str,
    sched_val,
    cert_val,
    winner: str,
):
    """
    Detect a conflict between two scalar values, record it, and return the winner's value.

    A conflict is logged only when both values are non-None *and* differ.
    ``winner`` must be ``"schedule"`` or ``"certificate"``.
    """
    if sched_val is not None and cert_val is not None:
        if _normalise(sched_val) != _normalise(cert_val):
            conflicts.append(ConflictEntry(
                field=field,
                schedule_value=str(sched_val),
                certificate_value=str(cert_val),
                winner=winner,
            ))
    if winner == "certificate":
        return _first(cert_val, sched_val)
    return _first(sched_val, cert_val)  # schedule wins (default)


def _find_matching_driver(name: str, candidates: list[Driver]) -> Driver | None:
    """
    Find the best-matching driver from *candidates* using fuzzy name matching.

    Uses ``rapidfuzz.fuzz.token_sort_ratio`` so middle-name or word-order
    differences (e.g. "JOHN A SMITH" vs "SMITH JOHN") still match.
    Returns None when the best score is below ``_DRIVER_NAME_MATCH_THRESHOLD``.
    """
    try:
        from rapidfuzz import fuzz as rfuzz
    except ImportError:
        # Graceful fallback: exact uppercase match (original behaviour)
        upper = name.strip().upper()
        return next((d for d in candidates if d.name.strip().upper() == upper), None)

    best_score = 0
    best_driver: Driver | None = None
    for candidate in candidates:
        score = rfuzz.token_sort_ratio(name.strip(), candidate.name.strip())
        if score > best_score:
            best_score = score
            best_driver = candidate
    return best_driver if best_score >= _DRIVER_NAME_MATCH_THRESHOLD else None


def _merge_policy_header(
    sched: UKMotorGoldenRecord,
    cert: UKMotorGoldenRecord,
    conflicts: list[ConflictEntry],
) -> Optional[PolicyHeader]:
    """Schedule is master; fill any gap from Certificate."""
    sh = sched.policy_header or PolicyHeader()
    ch = cert.policy_header or PolicyHeader()

    poc: Optional[PeriodOfCover] = _first(sh.period_of_cover, ch.period_of_cover)

    return PolicyHeader(
        policy_number=_check_conflict(conflicts, "policy_header.policy_number", sh.policy_number, ch.policy_number, "schedule"),
        insurer=_check_conflict(conflicts, "policy_header.insurer", sh.insurer, ch.insurer, "schedule"),
        product_name=_check_conflict(conflicts, "policy_header.product_name", sh.product_name, ch.product_name, "schedule"),
        period_of_cover=poc,
    )


def _merge_drivers(
    sched: UKMotorGoldenRecord,
    cert: UKMotorGoldenRecord,
    conflicts: list[ConflictEntry],
) -> list[Driver]:
    """
    Schedule drivers are the base (they carry DOB, occupation, license_type).
    For each Schedule driver, fuzzy-match against Certificate drivers and enrich
    with relationship or is_main_driver if the Schedule record lacks them.
    Falls back to the Certificate list when Schedule has no drivers.

    Uses rapidfuzz ``token_sort_ratio`` with an 85-point threshold so minor
    name variations (initials, hyphenation, word order) still merge correctly.
    """
    sched_drivers = sched.driver_details or []
    cert_drivers = cert.driver_details or []

    if not sched_drivers:
        return cert_drivers

    merged: list[Driver] = []
    for sd in sched_drivers:
        cd = _find_matching_driver(sd.name, cert_drivers)

        if (
            cd is not None
            and sd.is_main_driver is not None
            and cd.is_main_driver is not None
            and sd.is_main_driver != cd.is_main_driver
        ):
            conflicts.append(ConflictEntry(
                field=f"driver_details[{sd.name}].is_main_driver",
                schedule_value=str(sd.is_main_driver),
                certificate_value=str(cd.is_main_driver),
                winner="schedule",
            ))

        merged.append(Driver(
            name=sd.name,
            dob=_first(sd.dob, cd.dob if cd else None),
            relationship=_first(sd.relationship, cd.relationship if cd else None),
            occupation=_first(sd.occupation, cd.occupation if cd else None),
            license_type=_first(sd.license_type, cd.license_type if cd else None),
            # Schedule wins, as recorded in the conflict entry above. Only a
            # missing value (None) is filled from the Certificate; an explicit
            # False on the Schedule is kept.
            is_main_driver=_first(sd.is_main_driver, cd.is_main_driver if cd else None),
            specific_excess=_first(sd.specific_excess, cd.specific_excess if cd else None),
        ))
    return merged


def _merge_cover_and_excesses(
    sched: UKMotorGoldenRecord,
    cert: UKMotorGoldenRecord,
    conflicts: list[ConflictEntry],
) -> Optional[CoverAndExcesses]:
    """
    Hybrid merge:
    - class_of_use, driving_other_cars  → Certificate is master
    - cover_type, NCB, excess_breakdown → Schedule is master
    """
    sc = sched.cover_and_excesses or CoverAndExcesses()
    cc = cert.cover_and_excesses or CoverAndExcesses()

    return CoverAndExcesses(
        cover_type=_check_conflict(conflicts, "cover_and_excesses.cover_type", sc.cover_type, cc.cover_type, "schedule"),
        no_claims_discount=_first(sc.no_claims_discount, cc.no_claims_discount),
        excess_breakdown=_first(sc.excess_breakdown, cc.excess_breakdown),
        # Certificate is authoritative for legal-use fields
        class_of_use=_check_conflict(conflicts, "cover_and_excesses.class_of_use", sc.class_of_use, cc.class_of_use, "certificate"),
        driving_other_cars=_check_conflict(conflicts, "cover_and_excesses.driving_other_cars", sc.driving_other_cars, cc.driving_other_cars, "certificate"),
    )
