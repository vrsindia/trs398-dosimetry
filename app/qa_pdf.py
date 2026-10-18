"""PDF reports for Daily QA and Mechanical QA sessions + weekly Daily QA."""
from __future__ import annotations

from datetime import datetime
from io import BytesIO
from typing import List, Optional


def _dept():
    try:
        from app.models import get_department
        return get_department()
    except Exception:
        return None


def _status_label(s: str) -> str:
    return {"green": "PASS", "yellow": "BORDERLINE", "red": "FAIL"}.get(
        (s or "").lower(), (s or "—").upper()
    )


def build_qa_session_pdf(session: dict) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
    )
    from reportlab.lib.enums import TA_CENTER

    dept = _dept()
    buf = BytesIO()
    kind = (session.get("kind") or "daily").lower()
    title_kind = "DAILY QA CHECKLIST" if kind == "daily" else "MECHANICAL QA"

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
        "T", parent=styles["Heading1"], fontSize=14, alignment=TA_CENTER,
        textColor=navy, fontName="Helvetica-Bold", spaceAfter=2,
    )
    sub = ParagraphStyle(
        "S", parent=styles["Normal"], fontSize=9, alignment=TA_CENTER,
        textColor=muted, spaceAfter=1,
    )
    section = ParagraphStyle(
        "Sec", parent=styles["Normal"], fontSize=10, textColor=navy,
        fontName="Helvetica-Bold", spaceBefore=8, spaceAfter=4,
    )
    normal = ParagraphStyle(
        "N", parent=styles["Normal"], fontSize=9, textColor=colors.HexColor("#2d3748"),
    )

    story = []
    hospital = getattr(dept, "hospital", None) or "Hospital / Cancer Centre"
    dept_name = getattr(dept, "name", None) or "Department of Radiation Oncology"
    story.append(Paragraph(hospital, title_style))
    story.append(Paragraph(dept_name, sub))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        'DOSE pro · Project "GARUDA" · VRS DOSIMETRY SOLUTIONS',
        ParagraphStyle("B", parent=sub, textColor=colors.HexColor("#2b6cb0"),
                       fontName="Helvetica-Oblique"),
    ))
    story.append(HRFlowable(width="100%", thickness=2, color=navy))
    story.append(Spacer(1, 6))
    story.append(Paragraph(title_kind + " REPORT", title_style))
    story.append(Spacer(1, 8))

    meta = [
        ["Machine", session.get("linac_name") or session.get("linac_id") or "—"],
        ["Date / time", (session.get("performed_at") or "")[:19].replace("T", " ")],
        ["Performed by", session.get("performed_by") or "—"],
        ["Overall", _status_label(session.get("overall") or "")],
    ]
    t = Table(meta, colWidths=[40 * mm, 120 * mm])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#2d3748")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(t)
    story.append(Spacer(1, 10))
    story.append(Paragraph("Checklist results", section))

    data = [["#", "Item", "Value", "Status"]]
    for i, r in enumerate(session.get("results") or [], 1):
        data.append([
            str(i),
            str(r.get("label") or "")[:48],
            str(r.get("display") or r.get("answer") or "—")[:24],
            _status_label(r.get("status") or ""),
        ])
    tbl = Table(data, colWidths=[12 * mm, 85 * mm, 40 * mm, 30 * mm])
    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), navy),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e0")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7fafc")]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    for ri, r in enumerate(session.get("results") or [], 1):
        st = (r.get("status") or "").lower()
        if st == "green":
            style_cmds.append(("TEXTCOLOR", (3, ri), (3, ri), colors.HexColor("#276749")))
        elif st == "yellow":
            style_cmds.append(("TEXTCOLOR", (3, ri), (3, ri), colors.HexColor("#975a16")))
        elif st == "red":
            style_cmds.append(("TEXTCOLOR", (3, ri), (3, ri), colors.HexColor("#c53030")))
    tbl.setStyle(TableStyle(style_cmds))
    story.append(tbl)

    if session.get("notes"):
        story.append(Spacer(1, 8))
        story.append(Paragraph("Notes", section))
        story.append(Paragraph(str(session["notes"]), normal))

    story.append(Spacer(1, 16))
    story.append(Paragraph(
        "Generated %s UTC" % datetime.utcnow().strftime("%Y-%m-%d %H:%M"),
        ParagraphStyle("F", parent=normal, fontSize=7, textColor=muted),
    ))

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()


def build_weekly_daily_qa_pdf(
    sessions: List[dict],
    week_start: str,
    week_end: str,
    linac_name: Optional[str] = None,
) -> bytes:
    """Combine multiple daily QA sessions for one week into one PDF."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, PageBreak,
    )
    from reportlab.lib.enums import TA_CENTER

    dept = _dept()
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
        "T", parent=styles["Heading1"], fontSize=14, alignment=TA_CENTER,
        textColor=navy, fontName="Helvetica-Bold", spaceAfter=2,
    )
    sub = ParagraphStyle(
        "S", parent=styles["Normal"], fontSize=9, alignment=TA_CENTER,
        textColor=muted, spaceAfter=1,
    )
    section = ParagraphStyle(
        "Sec", parent=styles["Normal"], fontSize=10, textColor=navy,
        fontName="Helvetica-Bold", spaceBefore=10, spaceAfter=4,
    )
    normal = ParagraphStyle(
        "N", parent=styles["Normal"], fontSize=9, textColor=colors.HexColor("#2d3748"),
    )

    story = []
    hospital = getattr(dept, "hospital", None) or "Hospital / Cancer Centre"
    dept_name = getattr(dept, "name", None) or "Department of Radiation Oncology"
    story.append(Paragraph(hospital, title_style))
    story.append(Paragraph(dept_name, sub))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        'DOSE pro · Project "GARUDA" · VRS DOSIMETRY SOLUTIONS',
        ParagraphStyle("B", parent=sub, textColor=colors.HexColor("#2b6cb0"),
                       fontName="Helvetica-Oblique"),
    ))
    story.append(HRFlowable(width="100%", thickness=2, color=navy))
    story.append(Spacer(1, 6))
    story.append(Paragraph("WEEKLY DAILY QA REPORT", title_style))
    story.append(Paragraph("%s → %s" % (week_start, week_end), sub))
    if linac_name:
        story.append(Paragraph("Machine: %s" % linac_name, sub))
    story.append(Spacer(1, 8))

    # Summary table
    story.append(Paragraph("Week summary", section))
    sum_data = [["Date", "Machine", "By", "Overall"]]
    for s in sessions:
        sum_data.append([
            (s.get("performed_at") or "")[:10],
            str(s.get("linac_name") or "")[:28],
            str(s.get("performed_by") or "")[:20],
            _status_label(s.get("overall") or ""),
        ])
    if len(sum_data) == 1:
        sum_data.append(["—", "No sessions", "—", "—"])
    stbl = Table(sum_data, colWidths=[28 * mm, 60 * mm, 45 * mm, 30 * mm])
    stbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), navy),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e0")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7fafc")]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(stbl)

    for idx, session in enumerate(sessions):
        story.append(Spacer(1, 12))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#a0aec0")))
        day = (session.get("performed_at") or "")[:10]
        story.append(Paragraph(
            "%s — %s — %s" % (
                day,
                session.get("linac_name") or "",
                _status_label(session.get("overall") or ""),
            ),
            section,
        ))
        story.append(Paragraph(
            "By: %s" % (session.get("performed_by") or "—"), normal,
        ))
        data = [["#", "Item", "Value", "Status"]]
        for i, r in enumerate(session.get("results") or [], 1):
            data.append([
                str(i),
                str(r.get("label") or "")[:48],
                str(r.get("display") or r.get("answer") or "—")[:24],
                _status_label(r.get("status") or ""),
            ])
        tbl = Table(data, colWidths=[12 * mm, 85 * mm, 40 * mm, 30 * mm])
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c5282")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cbd5e0")),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(tbl)

    story.append(Spacer(1, 16))
    story.append(Paragraph(
        "Generated %s UTC · %d session(s)" % (
            datetime.utcnow().strftime("%Y-%m-%d %H:%M"), len(sessions),
        ),
        ParagraphStyle("F", parent=normal, fontSize=7, textColor=muted),
    ))

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()
