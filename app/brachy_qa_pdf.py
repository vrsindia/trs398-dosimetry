"""PDF for a single Brachy Source QA annexure run."""
from __future__ import annotations

from datetime import datetime
from io import BytesIO
from typing import Any, Dict, List, Optional


def _dept():
    try:
        from app.models import get_department
        return get_department()
    except Exception:
        return None


def build_brachy_source_qa_pdf(session: dict) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
    )
    from reportlab.lib.enums import TA_CENTER, TA_LEFT

    dept = _dept()
    buf = BytesIO()
    annexure = session.get("annexure") or session.get("kind") or "Brachy Source QA"
    title = session.get("title") or annexure

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
    styles.add(ParagraphStyle(
        name="HCenter", parent=styles["Heading1"],
        alignment=TA_CENTER, fontSize=14, textColor=colors.HexColor("#1a365d"),
        spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        name="SubCenter", parent=styles["Normal"],
        alignment=TA_CENTER, fontSize=9, textColor=colors.HexColor("#4a5568"),
    ))
    styles.add(ParagraphStyle(
        name="Body", parent=styles["Normal"], fontSize=9, leading=12,
    ))

    story = []
    dept_name = getattr(dept, "name", None) or getattr(dept, "hospital_name", None) or ""
    if dept_name:
        story.append(Paragraph(str(dept_name), styles["HCenter"]))
    story.append(Paragraph("BRACHYTHERAPY SOURCE QA", styles["HCenter"]))
    story.append(Paragraph(str(title), styles["SubCenter"]))
    story.append(Spacer(1, 4 * mm))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#2b6cb0")))
    story.append(Spacer(1, 3 * mm))

    meta = [
        ["Annexure / test", str(annexure)],
        ["Performed at", str(session.get("performed_at") or "—")],
        ["Performed by", str(session.get("performed_by") or "—")],
        ["Overall", str(session.get("overall") or "—")],
        ["Machine", str(session.get("linac_name") or session.get("linac_id") or "—")],
    ]
    t = Table(meta, colWidths=[45 * mm, 120 * mm])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#2d3748")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(t)
    story.append(Spacer(1, 4 * mm))

    formula = session.get("formula") or ""
    if formula:
        story.append(Paragraph("<b>Formula:</b> %s" % formula, styles["Body"]))
        story.append(Spacer(1, 2 * mm))

    rows = [["Parameter", "Value"]]
    for item in session.get("results") or []:
        if isinstance(item, dict):
            rows.append([
                str(item.get("parameter") or item.get("name") or item.get("k") or ""),
                str(item.get("value") or item.get("v") or ""),
            ])
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            rows.append([str(item[0]), str(item[1])])

    if len(rows) > 1:
        tbl = Table(rows, colWidths=[90 * mm, 75 * mm])
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a365d")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e0")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7fafc")]),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(tbl)

    notes = session.get("notes") or ""
    if notes:
        story.append(Spacer(1, 4 * mm))
        story.append(Paragraph("<b>Notes:</b> %s" % notes, styles["Body"]))

    story.append(Spacer(1, 10 * mm))
    story.append(Paragraph(
        "Generated %s · Not stored as binary in database (session metadata only)."
        % datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        styles["SubCenter"],
    ))

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()
