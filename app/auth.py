"""auth.py — load known-good auth and rename section labels."""
import urllib.request

_URL = (
    "https://raw.githubusercontent.com/vrsindia/trs398-dosimetry/"
    "4826bee29eea42e5bb58f228c7682ee7abefa34e/app/auth.py"
)
_code = urllib.request.urlopen(_URL, timeout=30).read().decode("utf-8")
_code = _code.replace("Linac absolute dosimetry", "LINAC Output Measurement")
_code = _code.replace("linac absolute dosimetry", "LINAC Output Measurement")
_code = _code.replace("Absolute Dosimetry", "LINAC Output Measurement")
_code = _code.replace("absolute dosimetry", "output measurement")
exec(compile(_code, "app/auth.py", "exec"), globals())
