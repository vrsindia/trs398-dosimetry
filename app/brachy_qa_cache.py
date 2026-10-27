"""Short-lived cache of last brachy QA calculation per user (for Save after Calculate)."""
from __future__ import annotations

from typing import Any, Dict, Optional

_CACHE: Dict[str, dict] = {}


def put(username: str, section: str, payload: dict) -> None:
    key = "%s::%s" % (username or "anon", section)
    _CACHE[key] = payload


def get(username: str, section: str) -> Optional[dict]:
    key = "%s::%s" % (username or "anon", section)
    return _CACHE.get(key)


def pop(username: str, section: str) -> Optional[dict]:
    key = "%s::%s" % (username or "anon", section)
    return _CACHE.pop(key, None)
