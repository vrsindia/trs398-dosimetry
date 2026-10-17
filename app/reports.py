"""Professional PDF report generation for DOSE pro / GARUDA."""
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
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        HRFlowable, KeepTogether,
    )
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

    dept = get_department()
    buf = BytesIO()

    def _footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#1a365d"))
        canvas.setLineWidth(0.8)
        canvas.line(18 * mm, 14 * mm, A4[0] - 18 * mm, 14 * mm)
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#718096"))
        canvas.drawString(
            18 * mm, 9 * mm,
            'DOSE pro · Project "GARUDA" · VRS DOSIMETRY SOLUTIONS',
        )
        canvas.drawRightString(A4[0] - 18 * mm, 9 * mm, f"Page {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=16 * mm, rightMargin=16 * mm,
        topMargin=14 * mm, bottomMargin=20 * mm,
    )
    styles = getSampleStyleSheet()
    navy = colors.HexColor("#1a365d")
    muted = colors.HexColor("#4a5568")
    title_style = ParagraphStyle(
        "TitleCenter", parent=styles["Heading1"],
        fontSize=15, alignment=TA_CENTER, spaceAfter=2, textColor=navy,
        fontName="Helvetica-Bold",
    )
    sub_style = ParagraphStyle(
        "SubCenter", parent=styles["Normal"],
        fontSize=9, alignment=TA_CENTER, textColor=muted, spaceAfter=1,
    )
    brand_style = ParagraphStyle(
        "Brand", parent=styles["Normal"],
        fontSize=8, alignment=TA_CENTER, textColor=colors.HexColor("#2b6cb0"),
        spaceAfter=4, fontName="Helvetica-Oblique",
    )
    section = ParagraphStyle(
        "Section", parent=styles["Normal"],
        fontSize=10, textColor=navy, fontName="Helvetica-Bold",
        spaceBefore=8, spaceAfter=4,
    )
    normal = ParagraphStyle("Body", parent=styles["Normal"], fontSize=9, textColor=colors.HexColor("#2d3748"))
    small = ParagraphStyle("Small", parent=normal, fontSize=7.5, textColor=colors.HexColor("#718096"))

    story = []

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

    story.append(Spacer(1, 4))
    story.append(Paragraph('DOSE pro · Project "GARUDA" · VRS DOSIMETRY SOLUTIONS', brand_style))
    story.append(HRFlowable(width="100%", thickness=2, color=navy))
    story.append(Spacer(1, 6))
    story.append(Paragraph("ABSOLUTE DOSIMETRY REPORT", title_style))
    story.append(Paragraph("TRS-398 photon / electron output calibration", sub_style))
    story.append(Spacer(1, 8))

    meta = [
        ["Machine", report.linac_name or "—", "Report date", report.report_date or "—"],
        ["Prepared by", report.created_by or "—", "Generated", (report.created_at or "")[:19].replace("T", " ")],
        ["Modality", report.modality or "mixed", "Measurements", str(len(records))],
    ]
    meta_table = Table(meta, colWidths=[28 * mm, 58 * mm, 28 * mm, 58 * mm])
    meta_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#2d3748")),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f7fafc")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e0")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e2e8f0")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 10))

    story.append(Paragraph("Measurement results", section))
    header = ["Energy", "Mod.", "Avg (nC)", "Measured", "Final", "Nominal", "TPR", "Status", "Physicist"]
    data = [header]
    for r in records:
        final = r.tuned_output_cGy_MU if r.tuning_performed and r.tuned_output_cGy_MU else r.measured_output_cGy_MU
        status = {"pass": "PASS", "warning": "BORDER", "fail": "FAIL"}.get(r.status, "—")
        avg = f"{r.average_reading_nC:.3f}" if r.average_reading_nC else "—"
        tpr = f"{r.tpr20_10:.3f}" if r.tpr20_10 else "—"
        data.append([
            r.energy or "—",
            (r.modality or "—")[:6],
            avg,
            f"{r.measured_output_cGy_MU:.3f}",
            f"{final:.3f}",
            f"{r.nominal_output_cGy_MU:.3f}",
            tpr,
            status,
            (r.physicist or "—")[:14],
        ])
    if len(data) == 1:
        data.append(["—"] * 8 + ["No measurements"])

    col_w = [20 * mm, 16 * mm, 18 * mm, 18 * mm, 16 * mm, 16 * mm, 16 * mm, 16 * mm, 28 * mm]
    tbl = Table(data, colWidths=col_w, repeatRows=1)
    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), navy),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#a0aec0")),
        ("ALIGN", (2, 1), (7, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#edf2f7")]),
    ]
    # Colour status column
    for i, row in enumerate(data[1:], start=1):
        st = row[7] if len(row) > 7 else ""
        if st == "PASS":
            style_cmds.append(("TEXTCOLOR", (7, i), (7, i), colors.HexColor("#276749")))
            style_cmds.append(("FONTNAME", (7, i), (7, i), "Helvetica-Bold"))
        elif st == "FAIL":
            style_cmds.append(("TEXTCOLOR", (7, i), (7, i), colors.HexColor("#c53030")))
            style_cmds.append(("FONTNAME", (7, i), (7, i), "Helvetica-Bold"))
        elif st == "BORDER":
            style_cmds.append(("TEXTCOLOR", (7, i), (7, i), colors.HexColor("#c05621")))
            style_cmds.append(("FONTNAME", (7, i), (7, i), "Helvetica-Bold"))
    tbl.setStyle(TableStyle(style_cmds))
    story.append(tbl)

    if report.notes:
        story.append(Spacer(1, 8))
        story.append(Paragraph(f"<b>Notes:</b> {report.notes}", normal))

    story.append(Spacer(1, 22))
    sign = Table(
        [["_________________________", "_________________________"],
         ["Medical Physicist", "Reviewed / Approved by"],
         ["Date: _______________", "Date: _______________"]],
        colWidths=[85 * mm, 85 * mm],
    )
    sign.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 1), (-1, -1), 3),
        ("TEXTCOLOR", (0, 1), (-1, -1), muted),
    ]))
    story.append(sign)

    story.append(Spacer(1, 14))
    story.append(HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#cbd5e0")))
    story.append(Paragraph(
        "This report was generated by DOSE pro for internal quality assurance. "
        "Values must be reviewed and approved by a qualified medical physicist before clinical use.",
        small,
    ))
    story.append(Paragraph(
        'DOSE pro developed under project "GARUDA" by VRS DOSIMETRY SOLUTIONS.',
        small,
    ))

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()
