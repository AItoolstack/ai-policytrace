"""
tests/test_arbiter.py — Unit tests for PolicyArbiter.

These tests exercise the merge logic in isolation using pure fixture data,
with no LLM calls or file I/O.  Run with:

    pytest tests/test_arbiter.py -v

(From project root with the virtual-env activated.)
"""
from __future__ import annotations

import sys
from pathlib import Path

# Allow importing from src/ without installing the package
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest

from arbiter import PolicyArbiter
from schema import (
    AdditionalRiskData,
    ConflictEntry,
    CoverAndExcesses,
    Driver,
    ExcessBreakdown,
    FinancialSummary,
    NoClaimsDiscount,
    OptionalExtras,
    PeriodOfCover,
    PolicyHeader,
    UKMotorGoldenRecord,
    VehicleDetails,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_schedule(
    policy_number: str = "POL-001",
    insurer: str = "TestInsurer Ltd",
    cover_type: str = "Comprehensive",
    ncb_years: int = 3,
    class_of_use: str | None = None,
    drivers: list[dict] | None = None,
    excess_compulsory: float = 250.0,
    excess_voluntary: float = 150.0,
    premium: float = 600.0,
    vrm: str = "AB12 XYZ",
) -> UKMotorGoldenRecord:
    drv_list = [
        Driver(**d) for d in (drivers or [{"name": "ALICE SMITH", "is_main_driver": True}])
    ]
    return UKMotorGoldenRecord(
        policy_header=PolicyHeader(policy_number=policy_number, insurer=insurer),
        vehicle_details=VehicleDetails(vrm=vrm, make="Toyota", model="Corolla"),
        driver_details=drv_list,
        cover_and_excesses=CoverAndExcesses(
            cover_type=cover_type,
            class_of_use=class_of_use,
            no_claims_discount=NoClaimsDiscount(years=ncb_years, protected=False),
            excess_breakdown=ExcessBreakdown(
                standard_compulsory=excess_compulsory,
                voluntary=excess_voluntary,
                total_accidental_damage=excess_compulsory + excess_voluntary,
            ),
        ),
        financial_summary=FinancialSummary(
            total_annual_premium=premium,
            optional_extras=OptionalExtras(),
        ),
        additional_risk_data=AdditionalRiskData(home_ownership="Owned"),
    )


def _make_certificate(
    policy_number: str = "POL-001",
    class_of_use: str = "Social, Domestic and Pleasure",
    driving_other_cars: bool = False,
    drivers: list[dict] | None = None,
    insurer: str | None = None,
) -> UKMotorGoldenRecord:
    drv_list = [
        Driver(**d) for d in (drivers or [{"name": "ALICE SMITH", "is_main_driver": True}])
    ]
    return UKMotorGoldenRecord(
        policy_header=PolicyHeader(
            policy_number=policy_number,
            insurer=insurer,
        ),
        driver_details=drv_list,
        cover_and_excesses=CoverAndExcesses(
            class_of_use=class_of_use,
            driving_other_cars=driving_other_cars,
        ),
    )


# ---------------------------------------------------------------------------
# Basic merge tests
# ---------------------------------------------------------------------------

class TestBasicMerge:
    def test_returns_tuple_with_conflicts_list(self):
        arbiter = PolicyArbiter()
        sched = _make_schedule()
        cert = _make_certificate()
        result = arbiter.merge_records(sched, "sched.pdf", cert, "cert.pdf")
        assert isinstance(result, tuple)
        golden, conflicts = result
        assert isinstance(conflicts, list)

    def test_vehicle_details_from_schedule(self):
        arbiter = PolicyArbiter()
        sched = _make_schedule(vrm="AB12 XYZ")
        cert = _make_certificate()
        golden, _ = arbiter.merge_records(sched, "s.pdf", cert, "c.pdf")
        assert golden.vehicle_details is not None
        assert golden.vehicle_details.vrm == "AB12 XYZ"

    def test_class_of_use_from_certificate(self):
        arbiter = PolicyArbiter()
        sched = _make_schedule(class_of_use="Social")  # schedule has one
        cert = _make_certificate(class_of_use="Social, Domestic and Pleasure")  # cert is master
        golden, conflicts = arbiter.merge_records(sched, "s.pdf", cert, "c.pdf")
        assert golden.cover_and_excesses.class_of_use == "Social, Domestic and Pleasure"

    def test_cover_type_from_schedule(self):
        arbiter = PolicyArbiter()
        sched = _make_schedule(cover_type="Comprehensive")
        cert = _make_certificate()
        golden, _ = arbiter.merge_records(sched, "s.pdf", cert, "c.pdf")
        assert golden.cover_and_excesses.cover_type == "Comprehensive"

    def test_financial_summary_from_schedule(self):
        arbiter = PolicyArbiter()
        sched = _make_schedule(premium=750.0)
        cert = _make_certificate()
        golden, _ = arbiter.merge_records(sched, "s.pdf", cert, "c.pdf")
        assert golden.financial_summary.total_annual_premium == 750.0

    def test_additional_risk_data_from_schedule(self):
        arbiter = PolicyArbiter()
        sched = _make_schedule()
        cert = _make_certificate()
        golden, _ = arbiter.merge_records(sched, "s.pdf", cert, "c.pdf")
        assert golden.additional_risk_data.home_ownership == "Owned"


# ---------------------------------------------------------------------------
# One-sided merge (missing Schedule or Certificate)
# ---------------------------------------------------------------------------

class TestOneSidedMerge:
    def test_empty_schedule_uses_certificate_drivers(self):
        arbiter = PolicyArbiter()
        sched = UKMotorGoldenRecord()  # empty
        cert = _make_certificate(
            drivers=[{"name": "BOB JONES", "is_main_driver": True}]
        )
        golden, _ = arbiter.merge_records(sched, "s.pdf", cert, "c.pdf")
        assert len(golden.driver_details) == 1
        assert golden.driver_details[0].name == "BOB JONES"

    def test_empty_certificate_still_merges(self):
        arbiter = PolicyArbiter()
        sched = _make_schedule()
        cert = UKMotorGoldenRecord()  # empty
        golden, _ = arbiter.merge_records(sched, "s.pdf", cert, "c.pdf")
        assert golden.vehicle_details is not None
        assert golden.cover_and_excesses is not None

    def test_policy_number_fallback_to_certificate(self):
        arbiter = PolicyArbiter()
        sched = UKMotorGoldenRecord(policy_header=PolicyHeader(policy_number=None))
        cert = _make_certificate(policy_number="CERT-999")
        golden, _ = arbiter.merge_records(sched, "s.pdf", cert, "c.pdf")
        assert golden.policy_header.policy_number == "CERT-999"


# ---------------------------------------------------------------------------
# Conflict detection
# ---------------------------------------------------------------------------

class TestConflictDetection:
    def test_no_conflicts_when_values_match(self):
        arbiter = PolicyArbiter()
        sched = _make_schedule(policy_number="POL-001", insurer="Insurer A")
        cert = _make_certificate(policy_number="POL-001")
        _, conflicts = arbiter.merge_records(sched, "s.pdf", cert, "c.pdf")
        policy_number_conflicts = [c for c in conflicts if c.field == "policy_header.policy_number"]
        assert policy_number_conflicts == []

    def test_conflict_logged_for_differing_policy_numbers(self):
        arbiter = PolicyArbiter()
        sched = _make_schedule(policy_number="POL-001")
        cert = _make_certificate(policy_number="POL-002")
        golden, conflicts = arbiter.merge_records(sched, "s.pdf", cert, "c.pdf")
        conflict_fields = [c.field for c in conflicts]
        assert "policy_header.policy_number" in conflict_fields
        # Schedule wins
        assert golden.policy_header.policy_number == "POL-001"

    def test_conflict_entry_has_both_values(self):
        arbiter = PolicyArbiter()
        sched = _make_schedule(policy_number="SCHED-100")
        cert = _make_certificate(policy_number="CERT-200")
        _, conflicts = arbiter.merge_records(sched, "s.pdf", cert, "c.pdf")
        c = next(x for x in conflicts if x.field == "policy_header.policy_number")
        assert c.schedule_value == "SCHED-100"
        assert c.certificate_value == "CERT-200"
        assert c.winner == "schedule"

    def test_class_of_use_conflict_certificate_wins(self):
        arbiter = PolicyArbiter()
        sched = _make_schedule(class_of_use="Social Only")
        cert = _make_certificate(class_of_use="Social, Domestic and Pleasure")
        golden, conflicts = arbiter.merge_records(sched, "s.pdf", cert, "c.pdf")
        c = next((x for x in conflicts if x.field == "cover_and_excesses.class_of_use"), None)
        assert c is not None
        assert c.winner == "certificate"
        assert golden.cover_and_excesses.class_of_use == "Social, Domestic and Pleasure"


# ---------------------------------------------------------------------------
# Driver merging
# ---------------------------------------------------------------------------

class TestDriverMerge:
    def test_exact_name_match_enriches_driver(self):
        arbiter = PolicyArbiter()
        sched = _make_schedule(
            drivers=[{"name": "ALICE SMITH", "is_main_driver": True, "dob": None, "relationship": None}]
        )
        cert = _make_certificate(
            drivers=[{"name": "ALICE SMITH", "is_main_driver": True, "relationship": "Proposer"}]
        )
        golden, _ = arbiter.merge_records(sched, "s.pdf", cert, "c.pdf")
        assert golden.driver_details[0].relationship == "Proposer"

    def test_fuzzy_name_match_merges(self):
        """Names with minor differences (e.g. missing middle initial) should still match."""
        arbiter = PolicyArbiter()
        sched = _make_schedule(
            drivers=[{"name": "ALICE J SMITH", "is_main_driver": True}]
        )
        cert = _make_certificate(
            drivers=[{"name": "ALICE SMITH", "is_main_driver": True, "relationship": "Proposer"}]
        )
        golden, _ = arbiter.merge_records(sched, "s.pdf", cert, "c.pdf")
        assert golden.driver_details[0].relationship == "Proposer"

    def test_unmatched_driver_has_no_cert_enrichment(self):
        """A driver with a completely different name gets no cert data."""
        arbiter = PolicyArbiter()
        sched = _make_schedule(
            drivers=[{"name": "ALICE SMITH", "is_main_driver": True}]
        )
        cert = _make_certificate(
            drivers=[{"name": "BOB JONES", "is_main_driver": True, "relationship": "Spouse"}]
        )
        golden, _ = arbiter.merge_records(sched, "s.pdf", cert, "c.pdf")
        alice = golden.driver_details[0]
        assert alice.name == "ALICE SMITH"
        assert alice.relationship is None  # no cert match, so no enrichment


# ---------------------------------------------------------------------------
# field_citations merging
# ---------------------------------------------------------------------------

class TestFieldCitationsMerge:
    def test_schedule_citations_win_on_conflict(self):
        arbiter = PolicyArbiter()
        sched = _make_schedule()
        cert = _make_certificate()
        sched.field_citations = {
            "vehicle_details.vrm": "AB12 XYZ",
            "policy_header.policy_number": "POL-001 from schedule",
        }
        cert.field_citations = {
            "policy_header.policy_number": "POL-001 from cert",
            "cover_and_excesses.class_of_use": "Social, Domestic and Pleasure",
        }
        golden, _ = arbiter.merge_records(sched, "s.pdf", cert, "c.pdf")
        fc = golden.field_citations or {}
        # Schedule wins the shared key
        assert fc.get("policy_header.policy_number") == "POL-001 from schedule"
        # Cert-only key survives
        assert fc.get("cover_and_excesses.class_of_use") == "Social, Domestic and Pleasure"
        # Schedule-only key survives
        assert fc.get("vehicle_details.vrm") == "AB12 XYZ"

    def test_empty_citations_produce_none(self):
        arbiter = PolicyArbiter()
        sched = _make_schedule()
        cert = _make_certificate()
        golden, _ = arbiter.merge_records(sched, "s.pdf", cert, "c.pdf")
        # Neither side has citations → merged record has None
        assert golden.field_citations is None
