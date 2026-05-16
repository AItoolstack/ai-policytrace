"""
Generate a synthetic UK motor insurance PDF pack for demos and tests.

The PDFs are intentionally fictional: invented insurer, logo, names, address,
policy number, vehicle registration, and risk details. They are text-based PDFs
so Docling can parse them without OCR.

Run from the repository root:

    python scripts/generate_synthetic_policy_pack.py
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


OUT_DIR = Path("sample_data/policytrace_demo_pack")
BRAND_DARK = colors.HexColor("#1F2937")
BRAND_BLUE = colors.HexColor("#2563EB")
BRAND_TEAL = colors.HexColor("#008080")
BRAND_PINK = colors.HexColor("#FCE7F3")
BRAND_LIGHT = colors.HexColor("#F8FAFC")

POLICY = {
    "insurer": "Northbridge Mutual Motor Insurance Ltd",
    "product_name": "PolicyTrace Comprehensive Plus",
    "policy_number": "NBM-DEMO-0427",
    "issue_date": "18/03/2026",
    "start_date": "15/04/2026 at 00:00 hours",
    "expiry_date": "14/04/2027 at 23:59 hours",
    "policyholder": "Alex Morgan",
    "address": "14 Demo Crescent, Sampleton, West Yorkshire, ZZ1 1ZZ",
    "dob": "14/03/1991",
    "occupation": "Product Manager",
    "second_driver": "Priya Shah",
    "second_driver_dob": "07/08/1995",
    "second_driver_occupation": "Business Analyst",
    "third_driver": "Jordan Reed",
    "third_driver_dob": "11/10/1985",
    "third_driver_occupation": "Data Administrator",
    "vrm": "ZX24 DEM",
    "make": "Skoda",
    "model": "Enyaq iV 60 62kWh 177.0 bhp",
    "fuel_type": "Electric",
    "transmission": "Automatic",
    "estimated_value": "Market Value",
    "annual_mileage": "7,000 miles",
    "overnight_postcode": "ZZ1 1ZZ",
    "kept_location": "Drive",
    "security_device": "Yes",
    "tracker_fitted": "No",
    "modifications": "No",
    "cover_type": "Comprehensive",
    "class_of_use": (
        "Use for social, domestic and pleasure purposes including commuting "
        "to and from a permanent place of work."
    ),
    "driving_other_cars": "No",
    "ncb_years": "2 years",
    "ncb_protected": "No",
    "standard_compulsory": "GBP 395.00",
    "voluntary": "GBP 200.00",
    "total_accidental_damage": "GBP 595.00",
    "fire": "GBP 395.00",
    "theft": "GBP 445.00",
    "windscreen_repair": "GBP 15.00",
    "windscreen_replacement": "GBP 200.00",
    "own_repairer": "GBP 200.00",
    "total_premium": "GBP 703.28",
    "legal": "GBP 25.40",
    "breakdown": "GBP 28.07",
    "personal_accident": "GBP 20.00",
    "hire_car": "Not selected",
    "key_cover": "Not selected",
}


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "title",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=22,
            textColor=BRAND_DARK,
            spaceAfter=14,
        ),
        "subtitle": ParagraphStyle(
            "subtitle",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#475569"),
            spaceAfter=10,
        ),
        "h2": ParagraphStyle(
            "h2",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=13,
            textColor=BRAND_TEAL,
            spaceBefore=12,
            spaceAfter=7,
        ),
        "body": ParagraphStyle(
            "body",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=BRAND_DARK,
            spaceAfter=6,
        ),
        "small": ParagraphStyle(
            "small",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=7,
            leading=9,
            textColor=colors.HexColor("#64748B"),
        ),
    }


def _draw_header(canvas, doc, title: str) -> None:
    canvas.saveState()
    width, height = A4
    canvas.setFillColor(BRAND_DARK)
    canvas.roundRect(16 * mm, height - 24 * mm, 42 * mm, 11 * mm, 2 * mm, fill=1, stroke=0)
    canvas.setFillColor(BRAND_TEAL)
    canvas.circle(22 * mm, height - 18.5 * mm, 2.6 * mm, fill=1, stroke=0)
    canvas.setFillColor(BRAND_BLUE)
    canvas.circle(29 * mm, height - 18.5 * mm, 2.6 * mm, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 6)
    canvas.drawString(36 * mm, height - 19.5 * mm, "NORTHBRIDGE")
    canvas.setFillColor(colors.HexColor("#64748B"))
    canvas.setFont("Helvetica", 7)
    canvas.drawRightString(width - 16 * mm, height - 18 * mm, title)
    canvas.setStrokeColor(colors.HexColor("#E2E8F0"))
    canvas.line(16 * mm, height - 28 * mm, width - 16 * mm, height - 28 * mm)
    canvas.setFont("Helvetica", 6)
    canvas.setFillColor(colors.HexColor("#94A3B8"))
    canvas.drawString(
        16 * mm,
        11 * mm,
        "Synthetic demo document generated for AI Tool Stack PolicyTrace. No real customer or insurer data.",
    )
    canvas.drawRightString(width - 16 * mm, 11 * mm, f"Page {doc.page}")
    canvas.restoreState()


def _table(rows: Iterable[Iterable[str]], col_widths: list[float] | None = None) -> Table:
    data = [[Paragraph(str(cell), _styles()["body"]) for cell in row] for row in rows]
    table = Table(data, colWidths=col_widths, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), BRAND_LIGHT),
                ("TEXTCOLOR", (0, 0), (-1, 0), BRAND_DARK),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BRAND_PINK]),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def _doc(path: Path, title: str):
    return SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=32 * mm,
        bottomMargin=18 * mm,
        title=title,
        author="AI Tool Stack",
    )


def build_schedule() -> None:
    s = _styles()
    path = OUT_DIR / "Schedule of Insurance - Demo.pdf"
    story = [
        Paragraph("Car insurance schedule", s["title"]),
        Paragraph(
            "This schedule is a synthetic text-based PDF for the PolicyTrace demo. "
            "Please check all details carefully and contact Northbridge Mutual if anything is incorrect.",
            s["subtitle"],
        ),
        _table(
            [
                ["Policy number", POLICY["policy_number"], "Date of issue", POLICY["issue_date"]],
                ["Insurer", POLICY["insurer"], "Product", POLICY["product_name"]],
                ["Period of cover", f"{POLICY['start_date']} - {POLICY['expiry_date']}", "Cover type", POLICY["cover_type"]],
            ],
            [33 * mm, 52 * mm, 33 * mm, 52 * mm],
        ),
        Paragraph("Policyholder details", s["h2"]),
        _table(
            [
                ["Name", POLICY["policyholder"]],
                ["Address", POLICY["address"]],
                ["Date of birth", POLICY["dob"]],
                ["Occupation", POLICY["occupation"]],
                ["Children under 16", "Yes"],
                ["Home ownership status", "Not a Homeowner"],
                ["Number of cars in household", "1"],
                ["Access to other vehicles", "No access to any other vehicles"],
            ],
            [55 * mm, 115 * mm],
        ),
        Paragraph("Vehicle details", s["h2"]),
        _table(
            [
                ["Registration number", POLICY["vrm"], "Make", POLICY["make"]],
                ["Model", POLICY["model"], "Fuel type", POLICY["fuel_type"]],
                ["Transmission", POLICY["transmission"], "Estimated value", POLICY["estimated_value"]],
                ["Annual mileage", POLICY["annual_mileage"], "Overnight postcode", POLICY["overnight_postcode"]],
                ["Kept location", POLICY["kept_location"], "Security device fitted", POLICY["security_device"]],
                ["Tracker fitted", POLICY["tracker_fitted"], "Modifications", POLICY["modifications"]],
            ],
            [38 * mm, 48 * mm, 38 * mm, 48 * mm],
        ),
        Paragraph("Cover and no claims discount", s["h2"]),
        _table(
            [
                ["Class of use", POLICY["class_of_use"]],
                ["Driving other cars", POLICY["driving_other_cars"]],
                ["No claims discount", POLICY["ncb_years"]],
                ["Protected no claims discount", POLICY["ncb_protected"]],
            ],
            [55 * mm, 115 * mm],
        ),
        Paragraph("Excess breakdown", s["h2"]),
        _table(
            [
                ["Excess type", "Amount"],
                ["Standard compulsory excess", POLICY["standard_compulsory"]],
                ["Voluntary excess", POLICY["voluntary"]],
                ["Total accidental damage excess", POLICY["total_accidental_damage"]],
                ["Fire excess", POLICY["fire"]],
                ["Theft excess", POLICY["theft"]],
                ["Windscreen repair excess", POLICY["windscreen_repair"]],
                ["Windscreen replacement excess", POLICY["windscreen_replacement"]],
                ["Own repairer additional excess", POLICY["own_repairer"]],
            ],
            [90 * mm, 50 * mm],
        ),
        Paragraph("Driver details", s["h2"]),
        _table(
            [
                ["Driver name", "Date of birth", "Relationship", "Occupation", "Licence type", "Main driver", "Specific excess"],
                [POLICY["policyholder"], POLICY["dob"], "Policyholder", POLICY["occupation"], "Full Licence UK / 2/1 / No", "Yes", ""],
                [POLICY["second_driver"], POLICY["second_driver_dob"], "Named Driver", POLICY["second_driver_occupation"], "UK Provisional / 1/4 / No", "No", "GBP 200.00"],
                [POLICY["third_driver"], POLICY["third_driver_dob"], "Named Driver", POLICY["third_driver_occupation"], "Full Licence UK / 5/0 / No", "No", ""],
            ],
            [30 * mm, 24 * mm, 24 * mm, 31 * mm, 31 * mm, 18 * mm, 22 * mm],
        ),
        Paragraph("Financial summary", s["h2"]),
        _table(
            [
                ["Item", "Premium"],
                ["Total annual premium", POLICY["total_premium"]],
                ["Motor legal protection", POLICY["legal"]],
                ["Breakdown roadside assistance", POLICY["breakdown"]],
                ["Enhanced personal accident", POLICY["personal_accident"]],
                ["Hire car", POLICY["hire_car"]],
                ["Key cover", POLICY["key_cover"]],
            ],
            [90 * mm, 50 * mm],
        ),
    ]
    _doc(path, "Schedule of Insurance - Demo").build(
        story,
        onFirstPage=lambda c, d: _draw_header(c, d, "Schedule of Insurance"),
        onLaterPages=lambda c, d: _draw_header(c, d, "Schedule of Insurance"),
    )


def build_certificate() -> None:
    s = _styles()
    path = OUT_DIR / "Certificate of Motor Insurance - Demo.pdf"
    story = [
        Paragraph("Certificate of Motor Insurance", s["title"]),
        Paragraph(
            "This is to certify that a policy of insurance has been issued for the purposes of the Road Traffic Act.",
            s["subtitle"],
        ),
        _table(
            [
                ["Policy number", POLICY["policy_number"]],
                ["Insurer", POLICY["insurer"]],
                ["Effective from", POLICY["start_date"]],
                ["Expires", POLICY["expiry_date"]],
                ["Registration number", POLICY["vrm"]],
            ],
            [55 * mm, 115 * mm],
        ),
        Paragraph("Persons entitled to drive", s["h2"]),
        _table(
            [
                ["Name", "Entitlement"],
                [POLICY["policyholder"], "The policyholder may drive the insured vehicle."],
                [POLICY["second_driver"], "Named driver may drive the insured vehicle."],
                [POLICY["third_driver"], "Named driver may drive the insured vehicle."],
            ],
            [55 * mm, 115 * mm],
        ),
        Paragraph("Limitations as to use", s["h2"]),
        Paragraph(POLICY["class_of_use"], s["body"]),
        Paragraph("The policy does not provide cover for driving other cars.", s["body"]),
        Spacer(1, 8),
        Paragraph(
            "This certificate is fictional and is provided only as a safe demonstration fixture for the PolicyTrace project.",
            s["small"],
        ),
    ]
    _doc(path, "Certificate of Motor Insurance - Demo").build(
        story,
        onFirstPage=lambda c, d: _draw_header(c, d, "Certificate of Motor Insurance"),
        onLaterPages=lambda c, d: _draw_header(c, d, "Certificate of Motor Insurance"),
    )


def build_statement_of_fact() -> None:
    s = _styles()
    path = OUT_DIR / "Statement of Fact - Demo.pdf"
    story = [
        Paragraph("Statement of Fact", s["title"]),
        Paragraph(
            "These fictional facts were used to calculate the demo insurance premium.",
            s["subtitle"],
        ),
        _table(
            [
                ["Policy number", POLICY["policy_number"]],
                ["Main driver", POLICY["policyholder"]],
                ["Annual mileage", POLICY["annual_mileage"]],
                ["Vehicle kept overnight", POLICY["kept_location"]],
                ["Overnight postcode", POLICY["overnight_postcode"]],
                ["Security device fitted", POLICY["security_device"]],
                ["Tracker fitted", POLICY["tracker_fitted"]],
                ["Modifications", POLICY["modifications"]],
                ["Non-motoring convictions", "No"],
                ["Endorsements", "None"],
                ["Claims in last five years", "None"],
            ],
            [58 * mm, 112 * mm],
        ),
    ]
    _doc(path, "Statement of Fact - Demo").build(
        story,
        onFirstPage=lambda c, d: _draw_header(c, d, "Statement of Fact"),
        onLaterPages=lambda c, d: _draw_header(c, d, "Statement of Fact"),
    )


def build_policy_booklet() -> None:
    s = _styles()
    path = OUT_DIR / "Policy Booklet - Demo.pdf"
    story = [
        Paragraph("Motor Insurance Policy Booklet", s["title"]),
        Paragraph(
            "This booklet describes generic terms for a fictional motor insurance product. "
            "It intentionally contains little policyholder-specific data.",
            s["subtitle"],
        ),
        Paragraph("What is covered", s["h2"]),
        Paragraph(
            "Comprehensive cover may include damage to your vehicle, fire, theft, windscreen cover, "
            "and third-party liability, subject to the terms and exclusions in this booklet.",
            s["body"],
        ),
        Paragraph("Claims", s["h2"]),
        Paragraph(
            "You must tell Northbridge Mutual Motor Insurance Ltd about any accident or loss as soon as possible. "
            "We may ask for evidence, photographs, repair estimates, or further information.",
            s["body"],
        ),
        Paragraph("General exclusions", s["h2"]),
        Paragraph(
            "No cover is provided where the vehicle is used outside the permitted class of use, "
            "where the driver is not entitled to drive, or where policy information is materially incorrect.",
            s["body"],
        ),
        Paragraph("Complaints", s["h2"]),
        Paragraph(
            "If you are unhappy with our service, contact the fictional complaints team at Northbridge Mutual.",
            s["body"],
        ),
    ]
    _doc(path, "Policy Booklet - Demo").build(
        story,
        onFirstPage=lambda c, d: _draw_header(c, d, "Policy Booklet"),
        onLaterPages=lambda c, d: _draw_header(c, d, "Policy Booklet"),
    )


def write_manifest() -> None:
    manifest = {
        "purpose": "Synthetic demo data for AI Tool Stack PolicyTrace.",
        "warning": "No real customer, insurer, vehicle, or policy data is included.",
        "files": [
            "Schedule of Insurance - Demo.pdf",
            "Certificate of Motor Insurance - Demo.pdf",
            "Statement of Fact - Demo.pdf",
            "Policy Booklet - Demo.pdf",
        ],
        "expected_policy_number": POLICY["policy_number"],
        "expected_vrm": POLICY["vrm"],
        "expected_insurer": POLICY["insurer"],
    }
    (OUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    build_schedule()
    build_certificate()
    build_statement_of_fact()
    build_policy_booklet()
    write_manifest()
    print(f"Synthetic demo pack written to {OUT_DIR.resolve()}")


if __name__ == "__main__":
    main()
