"""
schema.py — Canonical Pydantic V2 data models for UK Motor Insurance extraction.

UKMotorGoldenRecord is the top-level output produced by the pipeline.
All sub-model fields are Optional to support partial per-document extractions;
the Arbiter produces the final complete record.

DocumentType and SourceMetadata are internal provenance types excluded from
the serialised Golden Record output (source_document uses Field(exclude=True)).
"""
from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Dict, List, Optional, Union

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Internal provenance (not in the serialised output)
# ---------------------------------------------------------------------------


class DocumentType(str, Enum):
    """Source document classification used for provenance and priority routing."""

    SCHEDULE = "Schedule"
    CERTIFICATE = "Certificate"
    STATEMENT_OF_FACT = "StatementOfFact"
    POLICY_BOOKLET = "PolicyBooklet"
    UNKNOWN = "Unknown"


class SourceMetadata(BaseModel):
    """Attached to every extraction so the arbiter can trace data lineage."""

    document_type: DocumentType = DocumentType.UNKNOWN
    filename: str = ""
    page_count: Optional[int] = None


# ---------------------------------------------------------------------------
# Golden Record sub-models
# ---------------------------------------------------------------------------


class PeriodOfCover(BaseModel):
    start_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None
    issue_date: Optional[date] = None


class PolicyHeader(BaseModel):
    policy_number: Optional[str] = None
    insurer: Optional[str] = None
    product_name: Optional[str] = None
    period_of_cover: Optional[PeriodOfCover] = None


class SecurityDetails(BaseModel):
    has_security_device: Optional[bool] = None
    tracker_fitted: Optional[bool] = None
    modifications: Optional[str] = None


class VehicleDetails(BaseModel):
    vrm: Optional[str] = None
    make: Optional[str] = None
    model: Optional[str] = None
    fuel_type: Optional[str] = None
    transmission: Optional[str] = None
    estimated_value: Optional[str] = None
    annual_mileage: Optional[int] = None
    overnight_postcode: Optional[str] = None
    kept_location: Optional[str] = None
    security: Optional[SecurityDetails] = None


class Driver(BaseModel):
    name: str
    dob: Optional[date] = None
    relationship: Optional[str] = None
    occupation: Optional[str] = None
    license_type: Optional[str] = None
    is_main_driver: Optional[bool] = None  # None = the document did not say
    specific_excess: Optional[float] = None


class NoClaimsDiscount(BaseModel):
    years: Optional[int] = None
    protected: Optional[bool] = None


class ExcessBreakdown(BaseModel):
    standard_compulsory: Optional[float] = None
    voluntary: Optional[float] = None
    total_accidental_damage: Optional[float] = None
    fire: Optional[float] = None
    theft: Optional[float] = None
    windscreen_repair: Optional[float] = None
    windscreen_replacement: Optional[float] = None
    own_repairer_additional_excess: Optional[float] = None


class CoverAndExcesses(BaseModel):
    cover_type: Optional[str] = None
    class_of_use: Optional[str] = None
    driving_other_cars: Optional[bool] = None
    no_claims_discount: Optional[NoClaimsDiscount] = None
    excess_breakdown: Optional[ExcessBreakdown] = None


class OptionalExtras(BaseModel):
    motor_legal_protection: Optional[Union[float, str]] = None
    breakdown_roadside_assistance: Optional[Union[float, str]] = None
    enhanced_personal_accident: Optional[Union[float, str]] = None
    hire_car: Optional[Union[float, str]] = None
    key_cover: Optional[Union[float, str]] = None


class FinancialSummary(BaseModel):
    total_annual_premium: Optional[float] = None
    optional_extras: Optional[OptionalExtras] = None


class AdditionalRiskData(BaseModel):
    home_ownership: Optional[str] = None
    children_under_16: Optional[bool] = None
    number_of_cars_in_household: Optional[int] = None
    non_motoring_convictions: Optional[bool] = None
    endorsements: Optional[str] = None


# ---------------------------------------------------------------------------
# Top-level Golden Record
# ---------------------------------------------------------------------------


class UKMotorGoldenRecord(BaseModel):
    """
    Final authoritative policy record produced by the Arbiter.

    All section fields are Optional so that partial per-document extractions
    remain valid Pydantic objects.  source_document is internal provenance
    and is excluded from model_dump_json().
    """

    policy_header: Optional[PolicyHeader] = None
    vehicle_details: Optional[VehicleDetails] = None
    driver_details: List[Driver] = Field(default_factory=list)
    cover_and_excesses: Optional[CoverAndExcesses] = None
    financial_summary: Optional[FinancialSummary] = None
    additional_risk_data: Optional[AdditionalRiskData] = None

    # Verbatim source quotes for provenance matching.
    # The LLM populates this mapping field_path → exact phrase copied from the document.
    # Used by provenance.py to locate each field in the PDF even when the extracted
    # value has been normalised (ISO dates, £ amounts, etc.).
    # Excluded from the final serialised output so it doesn't appear in downstream JSON.
    field_citations: Optional[Dict[str, str]] = Field(default=None, exclude=True)

    # Internal provenance — excluded from serialised output
    source_document: Optional[SourceMetadata] = Field(default=None, exclude=True)


# ---------------------------------------------------------------------------
# Provenance and Human-in-the-Loop review models
# ---------------------------------------------------------------------------


class Location(BaseModel):
    """Geometric location of a field's source text, in browser % coords (top-left origin)."""

    page: int
    bbox: List[float]  # [x0%, y0%, x1%, y1%]


class FieldProvenance(BaseModel):
    """Maps one Golden Record field to its source text element in the PDF."""

    field_path: str        # e.g. "vehicle_details.vrm"
    extracted_value: str   # the value produced by the LLM
    matched_text: str      # the corpus snippet that best matches it
    match_score: float     # 0.0–1.0 (1.0 = perfect)
    source_filename: str   # which PDF this came from
    location: Location     # page + bbox in browser % coords


class ConflictEntry(BaseModel):
    """Records a field where Schedule and Certificate held different values."""

    field: str                          # dotted field path, e.g. "policy_header.policy_number"
    schedule_value: Optional[str] = None
    certificate_value: Optional[str] = None
    winner: str                         # "schedule" | "certificate" | "fallback"


class GoldenRecordWithProvenance(BaseModel):
    """Full pipeline output for the Visual Audit Review UI."""

    record: UKMotorGoldenRecord
    provenance: List[FieldProvenance] = Field(default_factory=list)
    conflicts: List[ConflictEntry] = Field(default_factory=list)
    session_id: Optional[str] = None
