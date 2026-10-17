"""
provenance.py — Post-extraction provenance mapping for the Visual Audit UI.

After the LLM extracts a flat Golden Record, this module walks the record and
fuzzy-matches each extracted value against a ProvenanceCorpus built from the
Docling document IR.  The LLM is never asked to self-report geometry — that
would cause hallucinations; this module handles localisation as a pure
post-processing step.

Coordinate convention
─────────────────────
  Docling bbox  : PDF space — origin bottom-left, y increases upward, unit = pt
  Stored bbox   : Browser % — origin top-left, y increases downward, range 0–100

  Conversion (per axis):
      x0% = bbox.l / page_width  * 100
      y0% = (page_height - bbox.t) / page_height * 100   # top of element
      x1% = bbox.r / page_width  * 100
      y1% = (page_height - bbox.b) / page_height * 100   # bottom of element
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Iterator

logger = logging.getLogger(__name__)

# ── Matching parameters ──────────────────────────────────────────────────────
_MATCH_THRESHOLD = 78    # minimum rapidfuzz WRatio (0–100) for normalised-value fallback
_CITATION_THRESHOLD = 88 # minimum partial_ratio for LLM-supplied verbatim citation quotes
_MIN_VALUE_LEN = 4       # skip matching for values shorter than this (too ambiguous)

# Leaf field names whose values are boolean-like and would match too broadly
_SKIP_LEAF_NAMES = {
    "is_main_driver", "protected", "has_security_device",
    "tracker_fitted", "driving_other_cars",
}

# Top-level section names to skip entirely.
# `source_document` and `field_citations` are internal provenance fields —
# they don't contain verbatim PDF values so matching against them is meaningless.
_SKIP_SECTION_NAMES = {"source_document", "field_citations"}

# Docling labels that mark headings rather than values.
_HEADING_LABELS = {"title", "section_header", "page_header", "page_footer"}

# Document types whose corpora are unreliable for field-level matching.
# Policy Booklets contain generic boilerplate — matching against them produces
# false positives for almost every field ("Full", "UK", date digits, etc.).
_EXCLUDE_FROM_MATCHING: set[str] = {"PolicyBooklet", "Unknown"}

# Padding added to each bbox for display.  The Docling bbox is a tight text
# box (~1% page height per line) which is hard to see.  We expand it so the
# highlight is clearly visible without losing positional accuracy.
_BBOX_PAD_X = 0.4   # % to expand left/right
_BBOX_PAD_Y = 0.6   # % to expand top/bottom
_BBOX_MIN_H = 2.0   # % minimum height after padding


# ---------------------------------------------------------------------------
# Corpus data structures
# ---------------------------------------------------------------------------


@dataclass
class CorpusItem:
    """One text element from a Docling DoclingDocument, with browser % geometry."""

    text: str
    page: int
    bbox: list[float]       # [x0%, y0%, x1%, y1%] — top-left origin, 0–100
    source_filename: str
    label: str = ""         # Docling item label, e.g. "text", "section_header"


class ProvenanceCorpus:
    """All extractable text elements from one PDF, with their page geometry."""

    def __init__(self, source_filename: str = "", doc_type: str = "Unknown") -> None:
        self.source_filename = source_filename
        self.doc_type = doc_type   # e.g. "Schedule", "Certificate", "PolicyBooklet"
        self.items: list[CorpusItem] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_from_docling(self, doc: Any, filename: str) -> None:
        """
        Populate the corpus from a Docling DoclingDocument.

        Safely handles API variations across docling versions — logs a warning
        rather than propagating exceptions, so the calling pipeline stays alive
        even if provenance extraction fails.
        """
        self.source_filename = filename
        try:
            self._extract_items(doc, filename)
            logger.debug(
                "Corpus '%s': %d items, %d pages",
                filename, len(self.items), self._count_pages(doc),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Provenance extraction skipped for '%s': %s", filename, exc
            )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _extract_items(self, doc: Any, filename: str) -> None:
        page_sizes = _build_page_sizes(doc)
        if not page_sizes:
            logger.debug("No page size data for '%s' — provenance skipped", filename)
            return

        for item in _iter_items(doc):
            text = _item_text(item)
            if not text or len(text) < 2:
                continue
            for prov in getattr(item, "prov", []):
                self._add_prov_item(prov, text, filename, page_sizes, _item_label(item))

    def _add_prov_item(
        self,
        prov: Any,
        text: str,
        filename: str,
        page_sizes: dict[int, tuple[float, float]],
        label: str = "",
    ) -> None:
        page_no = getattr(prov, "page_no", None)
        if page_no is None:
            return
        page_no = int(page_no)
        if page_no not in page_sizes:
            return

        pw, ph = page_sizes[page_no]
        bbox = getattr(prov, "bbox", None)
        if bbox is None:
            return

        l   = float(getattr(bbox, "l", 0))
        t_v = float(getattr(bbox, "t", ph))  # top in PDF space  (high y value)
        r   = float(getattr(bbox, "r", pw))
        b   = float(getattr(bbox, "b", 0))   # bottom in PDF space (low y value)

        # Convert: PDF (bottom-left origin, pts) → browser % (top-left origin)
        x0 = _clamp(l   / pw * 100)
        y0 = _clamp((ph - t_v) / ph * 100)  # top of element in browser coords
        x1 = _clamp(r   / pw * 100)
        y1 = _clamp((ph - b)   / ph * 100)  # bottom of element in browser coords

        self.items.append(CorpusItem(
            text=text,
            page=page_no,
            bbox=[round(x0, 3), round(y0, 3), round(x1, 3), round(y1, 3)],
            source_filename=filename,
            label=label,
        ))

    @staticmethod
    def _count_pages(doc: Any) -> int:
        return len(getattr(doc, "pages", {}))


# ---------------------------------------------------------------------------
# Module-level helpers for corpus building
# ---------------------------------------------------------------------------


def _build_page_sizes(doc: Any) -> dict[int, tuple[float, float]]:
    sizes: dict[int, tuple[float, float]] = {}
    for page_no, page_item in getattr(doc, "pages", {}).items():
        size = getattr(page_item, "size", None)
        if size:
            w = float(getattr(size, "width", 0))
            h = float(getattr(size, "height", 0))
            if w > 0 and h > 0:
                sizes[int(page_no)] = (w, h)
    return sizes


def _iter_items(doc: Any):
    """Yield all document items, trying iterate_items() first then .texts/.tables."""
    try:
        for item, _level in doc.iterate_items():
            yield item
    except AttributeError:
        for item in getattr(doc, "texts", []):
            yield item
        for item in getattr(doc, "tables", []):
            yield item


def _item_text(item: Any) -> str:
    """Extract a string from a Docling TextItem or TableItem."""
    text = getattr(item, "text", None)
    if text is not None:
        return str(text).strip()
    # TableItem: concatenate all cell text into one searchable blob
    data = getattr(item, "data", None)
    if data is not None:
        cells = [
            str(getattr(cell, "text", "")).strip()
            for row in getattr(data, "grid", [])
            for cell in row
        ]
        return " | ".join(c for c in cells if c)
    return ""


def _item_label(item: Any) -> str:
    """Docling item label as a plain string ("" when unavailable)."""
    label = getattr(item, "label", "")
    return str(getattr(label, "value", label) or "")


def _norm(text: str) -> str:
    """Lowercase and collapse whitespace for containment checks."""
    return " ".join(str(text).split()).lower()


def _clamp(v: float) -> float:
    return max(0.0, min(100.0, v))


# ---------------------------------------------------------------------------
# Field-level provenance builder (main public function)
# ---------------------------------------------------------------------------


def build_provenance(
    record: Any,                         # UKMotorGoldenRecord
    corpora: list[ProvenanceCorpus],
) -> list[Any]:                          # list[FieldProvenance]
    """
    Walk the Golden Record and fuzzy-match each extracted value against all
    trusted corpora (Schedule, Certificate, StatementOfFact).

    Policy Booklet corpora are excluded — they contain generic boilerplate
    that produces false positives for almost every field value.

    Returns a ``FieldProvenance`` entry for every field that can be located
    above the match threshold.  Fields with no good corpus match are omitted —
    the UI shows them as "No location data".
    """
    from schema import FieldProvenance, Location  # local import avoids circular dep

    try:
        from rapidfuzz import fuzz as rfuzz
    except ImportError:
        logger.warning(
            "rapidfuzz not installed — provenance matching disabled. "
            "Run: pip install rapidfuzz"
        )
        return []

    # Filter to trusted corpora only (exclude Policy Booklet and Unknown docs)
    trusted_corpora = [
        c for c in corpora if c.doc_type not in _EXCLUDE_FROM_MATCHING
    ]
    if not trusted_corpora:
        logger.warning(
            "No trusted corpora available — all %d corpus/corpora are excluded "
            "(types: %s). Provenance will be empty.",
            len(corpora),
            [c.doc_type for c in corpora],
        )
        return []

    # LLM-supplied verbatim source quotes: field_path → raw text phrase.
    # These are always preferred over the normalised extracted value because
    # the LLM copies them directly from the document (e.g. "15/04/2026 at 00:00
    # hours" rather than the ISO "2026-04-15T00:00:00" we store in the record).
    citation_map: dict[str, str] = dict(getattr(record, "field_citations", None) or {})
    logger.info("  field_citations from LLM: %d entries", len(citation_map))

    results: list[FieldProvenance] = []
    citation_hits = 0
    # Track assigned positions to avoid two fields pointing to the same corpus item.
    # Key: (source_filename, page, x0, y0) — unpadded, original corpus position.
    used_positions: set[tuple] = set()
    driver_values = _driver_values(record)

    for field_path, value_str in _walk_record(record):
        leaf = field_path.split(".")[-1].strip("[]0123456789")
        if leaf in _SKIP_LEAF_NAMES:
            continue

        # Prefer the verbatim citation quote; fall back to the normalised value.
        # For ISO dates/datetimes also try UK DD/MM/YYYY format as a secondary fallback.
        search_str = citation_map.get(field_path, value_str)
        alt_search: str | None = None
        if field_path not in citation_map:
            alt_search = _iso_to_uk_date(value_str)

        if len(search_str) < _MIN_VALUE_LEN:
            continue

        using_citation = field_path in citation_map
        # When matching a citation quote use partial_ratio — the quote is a
        # verbatim substring of the document and WRatio penalises length disparity.
        # For normalised fallback values use WRatio to avoid short false matches.
        score_fn = rfuzz.partial_ratio if using_citation else rfuzz.WRatio
        threshold = _CITATION_THRESHOLD if using_citation else _MATCH_THRESHOLD

        # Rank candidates above the threshold by, in order:
        #   1. does the item contain the extracted value (or its UK date form)?
        #   2. is it ordinary text rather than a heading?
        #   3. for driver fields, how many of the same driver's other values it
        #      contains, so the field lands on that driver's row, not a label,
        #      a section heading or another driver's row;
        #   4. the fuzzy score.
        # A short label inside the quote ("Name" in "Named Driver") can score as
        # high as the real row, so the score alone is not enough.
        value_norm = _norm(value_str)
        uk_norm = _norm(_iso_to_uk_date(value_str) or "")
        driver_idx = _driver_index(field_path)
        sibling_values = [
            v for v in driver_values.get(driver_idx, []) if v and v != value_norm
        ] if driver_idx is not None else []

        def rank(item: CorpusItem, score: float) -> tuple:
            text_norm = _norm(item.text)
            covers = (len(value_norm) >= _MIN_VALUE_LEN and value_norm in text_norm) or (
                bool(uk_norm) and uk_norm in text_norm
            )
            not_heading = item.label not in _HEADING_LABELS
            row_bonus = sum(1 for v in sibling_values if v in text_norm)
            return (covers, not_heading, row_bonus, score)

        best_key: tuple | None = None
        best_item: CorpusItem | None = None
        best_unused_key: tuple | None = None
        best_unused_item: CorpusItem | None = None

        for corpus in trusted_corpora:
            for item in corpus.items:
                score = score_fn(search_str.lower(), item.text.lower())
                # Also try UK-formatted date if available
                if alt_search and score < threshold:
                    alt_score = rfuzz.partial_ratio(alt_search, item.text.lower())
                    if alt_score > score:
                        score = alt_score
                if score < threshold:
                    continue
                key = rank(item, score)
                pos_key = (item.source_filename, item.page, item.bbox[0], item.bbox[1])
                # Strictly greater: on a full tie the first item in reading order wins.
                if best_key is None or key > best_key:
                    best_key, best_item = key, item
                if pos_key not in used_positions and (best_unused_key is None or key > best_unused_key):
                    best_unused_key, best_unused_item = key, item

        # Prefer an unused position, but only if it is as good on everything
        # except the raw score. A driver's row is shared by several fields
        # (date of birth, relationship, occupation), and an unused heading
        # nearby must not win just because the row is already taken.
        if best_unused_item is not None and best_unused_key[:3] >= best_key[:3]:
            chosen_item, chosen_score = best_unused_item, best_unused_key[-1]
        elif best_item is not None:
            chosen_item, chosen_score = best_item, best_key[-1]
        else:
            continue

        pos_key = (chosen_item.source_filename, chosen_item.page, chosen_item.bbox[0], chosen_item.bbox[1])
        used_positions.add(pos_key)

        if using_citation:
            citation_hits += 1
        results.append(FieldProvenance(
            field_path=field_path,
            extracted_value=value_str,
            matched_text=chosen_item.text[:200],  # truncate very long table blobs
            match_score=round(chosen_score / 100.0, 3),
            source_filename=chosen_item.source_filename,
            location=Location(
                page=chosen_item.page,
                bbox=_padded_bbox(chosen_item.bbox),
            ),
        ))

    total = _count_total_fields(record)
    logger.info(
        "Provenance: %d / %d fields located (%d via citation quotes, %d via fuzzy fallback) "
        "— trusted corpora: %s",
        len(results), total,
        citation_hits, len(results) - citation_hits,
        [c.source_filename for c in trusted_corpora],
    )
    return results


# ---------------------------------------------------------------------------
# Field-walking helpers
# ---------------------------------------------------------------------------


def _walk_record(record: Any) -> Iterator[tuple[str, str]]:
    """Yield (field_path, string_value) for all non-None leaf values in the record."""
    data = record.model_dump(exclude_none=True)
    yield from _walk_dict(data, "")


def _walk_dict(d: dict, prefix: str) -> Iterator[tuple[str, str]]:
    for key, val in d.items():
        # Skip whole sections that produce unreliable or irrelevant matches
        top_key = prefix.split(".")[0].split("[")[0] if prefix else key
        if key in _SKIP_SECTION_NAMES or top_key in _SKIP_SECTION_NAMES:
            continue
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(val, dict):
            yield from _walk_dict(val, path)
        elif isinstance(val, list):
            yield from _walk_list(val, path)
        elif val is not None:
            yield path, str(val)


def _walk_list(lst: list, prefix: str) -> Iterator[tuple[str, str]]:
    for i, item in enumerate(lst):
        path = f"{prefix}[{i}]"
        if isinstance(item, dict):
            yield from _walk_dict(item, path)
        elif item is not None:
            yield path, str(item)


def _count_total_fields(record: Any) -> int:
    data = record.model_dump(exclude_none=True)
    return sum(1 for _ in _walk_dict(data, ""))


_DRIVER_PATH_RE = re.compile(r"^driver_details\[(\d+)\]\.")


def _driver_index(field_path: str) -> int | None:
    """Index of the driver a field belongs to, or None for non-driver fields."""
    m = _DRIVER_PATH_RE.match(field_path)
    return int(m.group(1)) if m else None


def _driver_values(record: Any) -> dict[int, list[str]]:
    """Normalised values per driver (UK date form for dates), used to keep a
    driver's fields on that driver's row. Names and booleans are left out:
    names are usually masked tokens and booleans match everywhere."""
    out: dict[int, list[str]] = {}
    for i, driver in enumerate(getattr(record, "driver_details", None) or []):
        vals: list[str] = []
        for key, val in driver.model_dump(exclude_none=True).items():
            if key == "name" or isinstance(val, bool):
                continue
            text = str(val)
            uk = _iso_to_uk_date(text)
            norm = _norm(uk or text)
            if len(norm) >= _MIN_VALUE_LEN:
                vals.append(norm)
        out[i] = vals
    return out


# ISO 8601 date/datetime patterns → UK DD/MM/YYYY
_ISO_DATE_RE = re.compile(r'^(\d{4})-(\d{2})-(\d{2})')


def _iso_to_uk_date(value: str) -> str | None:
    """Convert ISO date/datetime string to UK DD/MM/YYYY for document matching.

    Returns the UK-format string (e.g. "15/04/2026") if value looks like an
    ISO date, otherwise returns None.
    """
    m = _ISO_DATE_RE.match(value.strip())
    if m:
        yyyy, mm, dd = m.group(1), m.group(2), m.group(3)
        return f"{dd}/{mm}/{yyyy}"
    return None


def _padded_bbox(bbox: list[float]) -> list[float]:
    """Expand a tight Docling text bbox so highlights are clearly visible in the UI."""
    x0, y0, x1, y1 = bbox
    x0 = _clamp(x0 - _BBOX_PAD_X)
    y0 = _clamp(y0 - _BBOX_PAD_Y)
    x1 = _clamp(x1 + _BBOX_PAD_X)
    y1 = _clamp(y1 + _BBOX_PAD_Y)
    # Enforce minimum height so single-line text is always visible
    if (y1 - y0) < _BBOX_MIN_H:
        mid = (y0 + y1) / 2
        y0 = _clamp(mid - _BBOX_MIN_H / 2)
        y1 = _clamp(mid + _BBOX_MIN_H / 2)
    return [round(x0, 3), round(y0, 3), round(x1, 3), round(y1, 3)]
