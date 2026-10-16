"""
Professional report generation for DOSE pro (HTML primary; PDF/DOC downloadable content).
"""

from __future__ import annotations
from typing import List, Optional
from datetime import datetime
from app.models import (
    Report, OutputRecord, get_department, get_linac, get_beam, get_detector,
    list_output_records, add_report, _new_id,
)


def build_report_html(report: Report, records: List[OutputRecord]) -> str:
    dept = get_department()
    rows = ""
    for r in records:
        status_label = {"pass": "PASS", "warning": "BORDERLINE", "fail": "FAIL"}.get(r.status, "—")
        readings = ", ".join(f"{x:.4f}" for x in r.raw_readings) if r.raw_readings else "—"
        final = r.tuned_output_cGy_MU if r.tuning_performed and r.tuned_output_cGy_MU else r.measured_output_cGy_MU
        rows += f"""
        <tr>
            <td>{r.energy}</td>
            <td>{r.modality}</td>
            <td>{readings}</td>
            <td>{r.average_reading_nC:.4f if r.average_reading_nC else '—'}</td>
            <td>{r.measured_output_cGy_MU:.3f}</td>
            <td>{final:.3f}</td>
            <td>{r.nominal_output_cGy_MU:.3f}</td>
            <td>{r.tpr20_10:.4f if r.tpr20_10 else '—'}</td>
            <td>{status_label}</td>
            <td>{r.physicist}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{report.title}</title>
<style>
  body {{ font-family: 'Segoe UI', Arial, sans-serif; color: #1a202c; margin: 40px; font-size: 11pt; }}
  .header {{ border-bottom: 2px solid #1a365d; padding-bottom: 12px; margin-bottom: 20px; }}
  .header h1 {{ margin: 0; color: #1a365d; font-size: 18pt; }}
  .header .sub {{ color: #4a5568; font-size: 10pt; margin-top: 4px; }}
  .meta {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 20px; font-size: 10pt; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 9.5pt; }}
  th, td {{ border: 1px solid #cbd5e0; padding: 6px 8px; text-align: left; }}
  th {{ background: #edf2f7; color: #2d3748; }}
  .footer {{ margin-top: 30px; font-size: 9pt; color: #718096; border-top: 1px solid #e2e8f0; padding-top: 10px; }}
  .sign {{ margin-top: 40px; display: grid; grid-template-columns: 1fr 1fr; gap: 40px; }}
  .sign div {{ border-top: 1px solid #718096; padding-top: 6px; font-size: 9pt; }}
  @media print {{ body {{ margin: 15mm; }} }}
</style>
</head>
<body>
  <div class="header">
    <h1>DOSE pro — Absolute Dosimetry Report</h1>
    <div class="sub">{dept.name} · {dept.hospital}</div>
  </div>
  <div class="meta">
    <div><strong>Machine:</strong> {report.linac_name}</div>
    <div><strong>Report date:</strong> {report.report_date}</div>
    <div><strong>Prepared by:</strong> {report.created_by}</div>
    <div><strong>Generated:</strong> {report.created_at[:16]}</div>
  </div>
  <h2 style="font-size:12pt; color:#1a365d;">Measurement results</h2>
  <table>
    <tr>
      <th>Energy</th><th>Modality</th><th>Meter readings (nC)</th><th>Average (nC)</th>
      <th>Measured (cGy/MU)</th><th>Final (cGy/MU)</th><th>Nominal</th>
      <th>TPR20,10</th><th>Status</th><th>Physicist</th>
    </tr>
    {rows}
  </table>
  {f'<p style="margin-top:16px;"><strong>Notes:</strong> {report.notes}</p>' if report.notes else ''}
  <div class="sign">
    <div>Medical Physicist</div>
    <div>Reviewed by</div>
  </div>
  <div class="footer">
    DOSE pro Clinical Dosimetry Solution · {dept.city} {dept.country}<br>
    This report is generated for internal QA use. Validate before clinical decisions.
  </div>
</body>
</html>"""


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
