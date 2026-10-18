"""Patch reports.py titles to remove absolute dosimetry wording."""
import urllib.request

_URL = (
    "https://raw.githubusercontent.com/vrsindia/trs398-dosimetry/"
    "7a483805ad93b54d6c967f31a237219737b67eef/app/reports.py"
)

def _patched_code():
    code = urllib.request.urlopen(_URL, timeout=30).read().decode("utf-8")
    code = code.replace("Absolute Dosimetry —", "LINAC Output Measurement —")
    code = code.replace("ABSOLUTE DOSIMETRY REPORT", "LINAC OUTPUT MEASUREMENT REPORT")
    code = code.replace("Absolute Dosimetry", "LINAC Output Measurement")
    code = code.replace("absolute dosimetry", "output measurement")
    return code


def apply_reports_patch():
    """Replace app.reports module contents in-process."""
    import app.reports as reports_mod
    code = _patched_code()
    ns = dict(reports_mod.__dict__)
    exec(compile(code, "app/reports.py", "exec"), ns)
    for k, v in ns.items():
        if not k.startswith("__"):
            setattr(reports_mod, k, v)
    print("reports titles patched: LINAC Output Measurement")
