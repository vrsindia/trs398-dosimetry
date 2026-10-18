"""Runtime string overrides: never show 'absolute dosimetry' in UI/PDF titles."""

REPLACEMENTS = (
    ("Linac absolute dosimetry", "LINAC Output Measurement"),
    ("linac absolute dosimetry", "LINAC Output Measurement"),
    ("Absolute Dosimetry Report", "LINAC Output Measurement Report"),
    ("ABSOLUTE DOSIMETRY REPORT", "LINAC OUTPUT MEASUREMENT REPORT"),
    ("Absolute Dosimetry", "LINAC Output Measurement"),
    ("absolute dosimetry", "output measurement"),
)


def clean_text(s: str) -> str:
    if not s:
        return s
    out = s
    for a, b in REPLACEMENTS:
        out = out.replace(a, b)
    return out
