"""Professional PDF report generation for DOSE pro."""

from __future__ import annotations
from typing import List, Optional
from datetime import datetime
from io import BytesIO

from app.models import (
    Report, OutputRecord, get_department, get_linac,
    list_output_records, add_report, _new_id,
)


def create_report_from_date(linac_id: str, report_date: str, created_by: str,
                            notes: str = "", modality: str = "mixed") -> Optional[Report]:
    linac = get_linac(linac_id)
    if not linac:
        return None
    records = list_output_records(linac_id=linac_id, report_date=report_date, saved_only=True)
    if not records:
        records = list_output_records(linac_id=linac_id, report_date=report_date)
    title = f"Absolute Dosimetry — {linac.name} — {report_date}"
    rep = Report(
        id=_new_id(),
        linac_id=linac_id,
        linac_name=linac.name,
        report_date=report_date,
        created_at=datetime.utcnow().isoformat(),
        created_by=created_by,
        title=title,
        modality=modality,
        measurement_ids=[r.id for r in records],
        notes=notes,
        summary={"count": len(records)},
    )
    return add_report(rep)


def build_report_pdf(report: Report, records: List[OutputRecord]) -> bytes:
    """Generate professional PDF with hospital/department header."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.lib.enums import TA_CENTER, TA_LEFT

    dept = get_department()
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=16 * mm, bottomMargin=16 * mm,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TitleCenter", parent=styles["Heading1"],
        fontSize=14, alignment=TA_CENTER, spaceAfter=4, textColor=colors.HexColor("#1a365d"),
    )
    sub_style = ParagraphStyle(
        "SubCenter", parent=styles["Normal"],
        fontSize=10, alignment=TA_CENTER, textColor=colors.HexColor("#4a5568"), spaceAfter=2,
    )
    normal = styles["Normal"]
    small = ParagraphStyle("Small", parent=normal, fontSize=8, textColor=colors.HexColor("#718096"))

    story = []

    # Hospital / department header
    hospital = dept.hospital or "Hospital / Cancer Centre"
    dept_name = dept.name or "Department of Radiation Oncology"
    story.append(Paragraph(hospital, title_style))
    story.append(Paragraph(dept_name, sub_style))
    addr_parts = [p for p in [dept.address, dept.city, dept.country] if p]
    if addr_parts:
        story.append(Paragraph(", ".join(addr_parts), sub_style))
    contact = []
    if dept.phone:
        contact.append(f"Tel: {dept.phone}")
    if dept.email:
        contact.append(dept.email)
    if contact:
        story.append(Paragraph(" · ".join(contact), sub_style))
    if dept.head_physicist:
        story.append(Paragraph(f"Head of Physics: {dept.head_physicist}", sub_style))

    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#1a365d")))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Absolute Dosimetry Report", title_style))
    story.append(Paragraph("DOSE pro — Clinical Dosimetry Solution", sub_style))
    story.append(Spacer(1, 10))

    meta = [
        ["Machine:", report.linac_name, "Report date:", report.report_date],
        ["Prepared by:", report.created_by, "Generated:", (report.created_at or "")[:16]],
    ]
    meta_table = Table(meta, colWidths=[28 * mm, 55 * mm, 28 * mm, 55 * mm])
    meta_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#2d3748")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 12))

    story.append(Paragraph("<b>Measurement results</b>", normal))
    story.append(Spacer(1, 4))

    header = ["Energy", "Modality", "Avg (nC)", "Measured", "Final", "Nominal", "TPR20,10", "Status", "Physicist"]
    data = [header]
    for r in records:
        final = r.tuned_output_cGy_MU if r.tuning_performed and r.tuned_output_cGy_MU else r.measured_output_cGy_MU
        status = {"pass": "PASS", "warning": "BORDERLINE", "fail": "FAIL"}.get(r.status, "—")
        avg = f"{r.average_reading_nC:.4f}" if r.average_reading_nC else "—"
        tpr = f"{r.tpr20_10:.4f}" if r.tpr20_10 else "—"
        data.append([
            r.energy,
            r.modality,
            avg,
            f"{r.measured_output_cGy_MU:.3f}",
            f"{final:.3f}",
            f"{r.nominal_output_cGy_MU:.3f}",
            tpr,
            status,
            r.physicist or "—",
        ])

    if len(data) == 1:
        data.append(["—", "—", "—", "—", "—", "—", "—", "—", "No measurements"])

    col_w = [22 * mm, 20 * mm, 18 * mm, 18 * mm, 18 * mm, 18 * mm, 20 * mm, 22 * mm, 28 * mm]
    tbl = Table(data, colWidths=col_w, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#edf2f7")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e0")),
        ("ALIGN", (2, 1), (7, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7fafc")]),
    ]))
    story.append(tbl)

    if report.notes:
        story.append(Spacer(1, 10))
        story.append(Paragraph(f"<b>Notes:</b> {report.notes}", normal))

    story.append(Spacer(1, 28))
    sign = Table(
        [["_________________________", "_________________________"],
         ["Medical Physicist", "Reviewed by"]],
        colWidths=[80 * mm, 80 * mm],
    )
    sign.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 1), (-1, 1), 4),
    ]))
    story.append(sign)

    story.append(Spacer(1, 16))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#e2e8f0")))
    story.append(Paragraph(
        "DOSE pro Clinical Dosimetry Solution · For internal QA use. Validate before clinical decisions.",
        small,
    ))

    doc.build(story)
    return buf.getvalue()
