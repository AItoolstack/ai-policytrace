// ── Geometry ──────────────────────────────────────────────────────────────

export interface Location {
  page: number
  /** [x0%, y0%, x1%, y1%] — top-left origin, 0–100 range, percent of page */
  bbox: [number, number, number, number]
}

export interface FieldProvenance {
  field_path: string
  extracted_value: string
  matched_text: string
  /** 0.0–1.0 */
  match_score: number
  source_filename: string
  location: Location
}

// ── Golden Record sub-types ───────────────────────────────────────────────

export interface PeriodOfCover {
  start_date?: string
  expiry_date?: string
  issue_date?: string
}

export interface PolicyHeader {
  policy_number?: string
  insurer?: string
  product_name?: string
  period_of_cover?: PeriodOfCover
}

export interface SecurityDetails {
  has_security_device?: boolean
  tracker_fitted?: boolean
  modifications?: string
}

export interface VehicleDetails {
  vrm?: string
  make?: string
  model?: string
  fuel_type?: string
  transmission?: string
  estimated_value?: string
  annual_mileage?: number
  overnight_postcode?: string
  kept_location?: string
  security?: SecurityDetails
}

export interface Driver {
  name: string
  dob?: string
  relationship?: string
  occupation?: string
  license_type?: string
  is_main_driver: boolean
  specific_excess?: number
}

export interface NoClaimsDiscount {
  years?: number
  protected?: boolean
}

export interface ExcessBreakdown {
  standard_compulsory?: number
  voluntary?: number
  total_accidental_damage?: number
  fire?: number
  theft?: number
  windscreen_repair?: number
  windscreen_replacement?: number
  own_repairer_additional_excess?: number
}

export interface CoverAndExcesses {
  cover_type?: string
  class_of_use?: string
  driving_other_cars?: boolean
  no_claims_discount?: NoClaimsDiscount
  excess_breakdown?: ExcessBreakdown
}

export interface OptionalExtras {
  motor_legal_protection?: number | string
  breakdown_roadside_assistance?: number | string
  enhanced_personal_accident?: number | string
  hire_car?: number | string
  key_cover?: number | string
}

export interface FinancialSummary {
  total_annual_premium?: number
  optional_extras?: OptionalExtras
}

export interface AdditionalRiskData {
  home_ownership?: string
  children_under_16?: boolean
  number_of_cars_in_household?: number
  non_motoring_convictions?: boolean
  endorsements?: string
}

export interface Citations {
  vehicle_model?: string
  excess_details?: string
  class_of_use?: string
  driver_ages?: string
  premium_breakdown?: string
}

export interface GoldenRecord {
  policy_header?: PolicyHeader
  vehicle_details?: VehicleDetails
  driver_details: Driver[]
  cover_and_excesses?: CoverAndExcesses
  financial_summary?: FinancialSummary
  additional_risk_data?: AdditionalRiskData
  citations?: Citations
}

export interface ConflictEntry {
  field: string
  schedule_value?: string
  certificate_value?: string
  winner: 'schedule' | 'certificate' | 'fallback' | string
}

// ── Session ───────────────────────────────────────────────────────────────

export interface SessionData {
  record: GoldenRecord
  provenance: FieldProvenance[]
  conflicts?: ConflictEntry[]
  session_id: string
}

// ── Review state ──────────────────────────────────────────────────────────

export type ReviewAction = 'verify' | 'reject' | 'override'

export interface FieldReview {
  action: ReviewAction
  overridden_value?: string
  reviewer?: string
}

export type ReviewState = Record<string, FieldReview>

// ── Flat field entry (used by the form panel) ─────────────────────────────

export interface FieldEntry {
  fieldPath: string
  label: string
  value: string | null
  section: string
  provenance?: FieldProvenance
}

// ── API response types ────────────────────────────────────────────────────

export interface ProcessResponse {
  session_id: string
  fields_extracted: number
  provenance_coverage: number
}

export interface SampleFile {
  filename: string
  size_bytes: number
  url: string
}

export interface SamplePack {
  pack_name: string
  description: string
  warning: string
  expected_policy_number?: string
  expected_vrm?: string
  files: SampleFile[]
}
