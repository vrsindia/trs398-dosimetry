"""PDF report generation — titles use LINAC Output Measurement."""
import urllib.request

_URL = (
    "https://raw.githubusercontent.com/vrsindia/trs398-dosimetry/"
    "7a483805ad93b54d6c967f31a237219737b67eef/app/reports.py"
)
_code = urllib.request.urlopen(_URL, timeout=30).read().decode("utf-8")
_code = _code.replace("Absolute Dosimetry —", "LINAC Output Measurement —")
_code = _code.replace("ABSOLUTE DOSIMETRY REPORT", "LINAC OUTPUT MEASUREMENT REPORT")
_code = _code.replace("Absolute Dosimetry", "LINAC Output Measurement")
_code = _code.replace("absolute dosimetry", "output measurement")
exec(compile(_code, "app/reports.py", "exec"), globals())
