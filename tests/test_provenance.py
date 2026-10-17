"""
Tests for provenance matching (src/provenance.py).

The corpus below mirrors the synthetic demo Schedule: a policyholder section on
page 1 and a driver table on page 2 whose rows Docling returns as single text
items. These cases used to land on headings, labels or another driver's row.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from provenance import CorpusItem, ProvenanceCorpus, build_provenance  # noqa: E402
from schema import Driver, PolicyHeader, UKMotorGoldenRecord  # noqa: E402

_F = "Schedule of Insurance - Demo.pdf"


def _corpus() -> ProvenanceCorpus:
    corpus = ProvenanceCorpus(source_filename=_F, doc_type="Schedule")
    rows = [
        (1, "Policyholder details", "section_header"),
        (1, "Policy number", "text"),
        (1, "NBM-DEMO-0427", "text"),
        (1, "Name", "text"),
        (1, "Alex Morgan", "text"),
        (1, "14/03/1991", "text"),
        (1, "Product", "text"),
        (2, "Driver details", "section_header"),
        (2, "Driver name", "text"),
        (2, "14/03/1991 Policyholder Product Manager Full Licence UK / 2/1 / No Yes", "text"),
        (2, "07/08/1995 Named Driver Business Analyst UK Provisional / 1/4 / No No GBP 200.00", "text"),
        (2, "11/10/1985 Named Driver Data Administrator Full Licence UK / 5/0 / No No", "text"),
    ]
    for i, (page, text, label) in enumerate(rows):
        corpus.items.append(CorpusItem(
            text=text, page=page, bbox=[10.0, float(i * 5), 60.0, float(i * 5 + 2)],
            source_filename=_F, label=label,
        ))
    return corpus


def _record() -> UKMotorGoldenRecord:
    record = UKMotorGoldenRecord(
        policy_header=PolicyHeader(policy_number="NBM-DEMO-0427"),
        driver_details=[
            Driver(name="MASKED_PERSON_1", dob=date(1991, 3, 14), relationship="Policyholder",
                   occupation="Product Manager", license_type="Full UK", is_main_driver=True),
            Driver(name="MASKED_PERSON_2", dob=date(1995, 8, 7), relationship="Named Driver",
                   occupation="Business Analyst", license_type="UK Provisional"),
            Driver(name="MASKED_PERSON_3", dob=date(1985, 10, 11), relationship="Named Driver",
                   occupation="Data Administrator", license_type="Full UK"),
        ],
    )
    record.field_citations = {
        "driver_details[0].license_type": "Full Licence UK / 2/1 / No",
        "driver_details[2].license_type": "Full Licence UK / 5/0 / No",
    }
    return record


def _by_path() -> dict:
    return {p.field_path: p for p in build_provenance(_record(), [_corpus()])}


def test_policy_number_lands_on_value():
    assert _by_path()["policy_header.policy_number"].matched_text == "NBM-DEMO-0427"


def test_relationship_not_on_heading_or_label():
    prov = _by_path()
    assert prov["driver_details[0].relationship"].matched_text.startswith("14/03/1991 Policyholder")
    assert prov["driver_details[1].relationship"].matched_text.startswith("07/08/1995")
    assert prov["driver_details[2].relationship"].matched_text.startswith("11/10/1985")


def test_occupation_not_on_fragment():
    assert _by_path()["driver_details[0].occupation"].matched_text.startswith("14/03/1991 Policyholder")


def test_repeated_value_lands_on_the_right_drivers_row():
    prov = _by_path()
    assert prov["driver_details[0].license_type"].matched_text.startswith("14/03/1991")
    assert prov["driver_details[2].license_type"].matched_text.startswith("11/10/1985")


def test_masked_names_are_not_located():
    assert not any(p.endswith(".name") for p in _by_path())
