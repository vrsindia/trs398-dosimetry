"""Professional PDF report generation for DOSE pro / GARUDA."""
from __future__ import annotations
from typing import List, Optional, Any
from datetime import datetime
from io import BytesIO

from app.models import (
    Report, OutputRecord, get_department, get_linac,
    list_output_records, add_report, _new_id,
)


def create_report_from_date(
    linac_id: str,
    report_date: str,
    created_by: str,
    notes: str = "",
    modality: str = "mixed",
) -> Optional[Report]:
    linac = None
    try:
        linac = get_linac(linac_id)
    except Exception:
        linac = None
    if not linac:
        try:
            from app.models import list_linacs
            for m in list_linacs() or []:
                if str(getattr(m, "id", "")) == str(linac_id):
                    linac = m
                    break
        except Exception:
            pass
    if not linac:
        # minimal stub so report can still be created
        class _Stub:
            id = linac_id
            name = linac_id
        linac = _Stub()

    records: List[Any] = []
    try:
        records = list_output_records(
            linac_id=linac_id, report_date=report_date, saved_only=True,
        ) or []
        if not records:
            records = list_output_records(
                linac_id=linac_id, report_date=report_date,
            ) or []
    except Exception as e:
        print("create_report_from_date list:", e)
        records = []

    title = "Absolute Dosimetry — %s — %s" % (
        getattr(linac, "name", linac_id), report_date,
    )
    rep = Report(
        id=_new_id(),
        linac_id=str(linac_id),
        linac_name=getattr(linac, "name", linac_id) or str(linac_id),
        report_date=report_date,
        created_at=datetime.utcnow().isoformat(),
        created_by=created_by or "",
        title=title,
        modality=modality or "mixed",
        measurement_ids=[getattr(r, "id", "") for r in records if getattr(r, "id", None)],
        notes=notes or "",
        summary={"count": len(records)},
    )
    return add_report(rep)


def build_report_pdf(report: Report, records: List[Any]) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
    )
    from reportlab.lib.enums import TA_CENTER

    try:
        dept = get_department()
    except Exception:
        dept = None
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
        canvas.drawRightString(A4[0] - 18 * mm, 9 * mm, "Page %d" % doc.page)
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
    normal = ParagraphStyle(
        "Body", parent=styles["Normal"], fontSize=9, textColor=colors.HexColor("#2d3748"),
    )
    small = ParagraphStyle(
        "Small", parent=normal, fontSize=7.5, textColor=colors.HexColor("#718096"),
    )

    story = []
    hospital = getattr(dept, "hospital", None) or "Hospital / Cancer Centre"
    dept_name = getattr(dept, "name", None) or "Department of Radiation Oncology"
    story.append(Paragraph(str(hospital), title_style))
    story.append(Paragraph(str(dept_name), sub_style))
    addr_parts = [
        p for p in [
            getattr(dept, "address", None),
            getattr(dept, "city", None),
            getattr(dept, "country", None),
        ] if p
    ]
    if addr_parts:
        story.append(Paragraph(", ".join(str(x) for x in addr_parts), sub_style))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        'DOSE pro · Project "GARUDA" · VRS DOSIMETRY SOLUTIONS', brand_style,
    ))
    story.append(HRFlowable(width="100%", thickness=2, color=navy))
    story.append(Spacer(1, 6))
    story.append(Paragraph("ABSOLUTE DOSIMETRY REPORT", title_style))
    story.append(Paragraph("TRS-398 / clinical output documentation", sub_style))
    story.append(Spacer(1, 8))

    meta = [
        ["Machine", getattr(report, "linac_name", "") or "—"],
        ["Report date", getattr(report, "report_date", "") or "—"],
        ["Created", (getattr(report, "created_at", "") or "")[:19].replace("T", " ")],
        ["Created by", getattr(report, "created_by", "") or "—"],
        ["Measurements", str((getattr(report, "summary", None) or {}).get("count", len(records or [])))],
    ]
    t = Table(meta, colWidths=[40 * mm, 120 * mm])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#2d3748")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(t)
    story.append(Spacer(1, 10))
    story.append(Paragraph("Measurement results", section))

    data = [["#", "Energy", "Modality", "Measured", "Tuned", "Nominal", "Physicist", "Status"]]
    for i, r in enumerate(records or [], 1):
        measured = getattr(r, "measured_output_cGy_MU", None)
        tuned = getattr(r, "tuned_output_cGy_MU", None)
        nominal = getattr(r, "nominal_output_cGy_MU", None)
        st = (getattr(r, "status", "") or "").lower()
        st_label = {"pass": "PASS", "ok": "PASS", "fail": "FAIL", "border": "BORDER"}.get(st, (st or "—").upper())
        data.append([
            str(i),
            str(getattr(r, "energy", "") or "—"),
            str(getattr(r, "modality", "") or "—"),
            ("%.3f" % measured) if measured is not None else "—",
            ("%.3f" % tuned) if tuned is not None else "—",
            ("%.3f" % nominal) if nominal is not None else "—",
            str(getattr(r, "physicist", "") or "—")[:18],
            st_label,
        ])
    if len(data) == 1:
        data.append(["—", "No measurements for this date", "—", "—", "—", "—", "—", "—"])

    tbl = Table(data, colWidths=[10*mm, 22*mm, 22*mm, 22*mm, 22*mm, 22*mm, 28*mm, 20*mm])
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

    if getattr(report, "notes", None):
        story.append(Spacer(1, 8))
        story.append(Paragraph("<b>Notes:</b> %s" % report.notes, normal))

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
