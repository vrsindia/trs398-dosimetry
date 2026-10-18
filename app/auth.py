"""
User authentication, roles and permissions for DOSE pro.
In-memory store – suitable for single-instance free-tier deployment.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
from datetime import datetime
import hashlib
import secrets
import uuid


ROLES = (
    "developer", "admin", "physicist", "doctor", "technologist", "intern", "observer",
)

PERM_CALCULATE = "calculate"
PERM_TUNE = "tune"
PERM_LIBRARY_VIEW = "library_view"
PERM_LIBRARY_EDIT = "library_edit"
PERM_APPROVE = "approve"
PERM_USER_MANAGE = "user_manage"
PERM_DEPT_EDIT = "dept_edit"
PERM_HISTORY_VIEW = "history_view"
PERM_ADMIN_PANEL = "admin_panel"

SEC_LINAC = "sec_linac"
SEC_BRACHY = "sec_brachy"
SEC_ACTIVITY = "sec_activity"
SEC_BED = "sec_bed"
SEC_BED_COMBINED = "sec_bed_combined"
SEC_GAP = "sec_gap"
SEC_FRACTIONATION = "sec_fractionation"
SEC_EQSQUARE = "sec_eqsquare"
SEC_MU = "sec_mu"
SEC_UNITS = "sec_units"
SEC_NT = "sec_nt_constraints"
SEC_LIBRARIES = "sec_libraries"
SEC_HISTORY = "sec_history"
SEC_REPORTS = "sec_reports"
SEC_APPROVALS = "sec_approvals"
SEC_DEPARTMENT = "sec_department"

SECTION_LABELS = {
    SEC_LINAC: "LINAC Output Measurement",
    SEC_BRACHY: "Brachytherapy",
    SEC_ACTIVITY: "Source activity",
    SEC_BED: "BED / EQD2",
    SEC_BED_COMBINED: "EBRT + brachy BED",
    SEC_GAP: "Gap correction",
    SEC_FRACTIONATION: "Fractionation pattern",
    SEC_EQSQUARE: "Equivalent square",
    SEC_MU: "MU calculator",
    SEC_UNITS: "Units converter",
    SEC_NT: "OAR constraints",
    SEC_LIBRARIES: "Libraries",
    SEC_HISTORY: "Output history",
    SEC_REPORTS: "Reports",
    SEC_APPROVALS: "Approvals",
    SEC_DEPARTMENT: "Department",
}

ALL_SECTION_PERMS = list(SECTION_LABELS.keys())

PERM_LABELS = {
    PERM_CALCULATE: "Run calculations",
    PERM_TUNE: "Tune output",
    PERM_LIBRARY_VIEW: "View libraries",
    PERM_LIBRARY_EDIT: "Edit libraries",
    PERM_APPROVE: "Approve changes",
    PERM_USER_MANAGE: "Manage users",
    PERM_DEPT_EDIT: "Edit department",
    PERM_HISTORY_VIEW: "View history",
    PERM_ADMIN_PANEL: "User directory",
}

DEFAULT_PERMISSIONS: Dict[str, Set[str]] = {
    "developer": {
        PERM_CALCULATE, PERM_TUNE, PERM_LIBRARY_VIEW, PERM_LIBRARY_EDIT,
        PERM_APPROVE, PERM_USER_MANAGE, PERM_DEPT_EDIT, PERM_HISTORY_VIEW,
        PERM_ADMIN_PANEL,
        *ALL_SECTION_PERMS,
    },
    "admin": {
        PERM_CALCULATE, PERM_TUNE, PERM_LIBRARY_VIEW, PERM_LIBRARY_EDIT,
        PERM_APPROVE, PERM_USER_MANAGE, PERM_DEPT_EDIT, PERM_HISTORY_VIEW,
        PERM_ADMIN_PANEL,
        *ALL_SECTION_PERMS,
    },
    "physicist": {
        PERM_CALCULATE, PERM_TUNE, PERM_LIBRARY_VIEW, PERM_LIBRARY_EDIT,
        PERM_APPROVE, PERM_HISTORY_VIEW,
        *ALL_SECTION_PERMS,
    },
    "doctor": {
        PERM_CALCULATE, PERM_LIBRARY_VIEW, PERM_HISTORY_VIEW,
        SEC_BED, SEC_BED_COMBINED, SEC_GAP, SEC_FRACTIONATION, SEC_NT,
        SEC_HISTORY, SEC_REPORTS,
    },
    "technologist": {
        PERM_CALCULATE, PERM_LIBRARY_VIEW, PERM_HISTORY_VIEW,
        SEC_LINAC, SEC_BRACHY, SEC_ACTIVITY, SEC_HISTORY, SEC_REPORTS,
    },
    "intern": {
        PERM_CALCULATE, PERM_LIBRARY_VIEW, PERM_HISTORY_VIEW,
        SEC_LINAC, SEC_BRACHY, SEC_ACTIVITY, SEC_BED, SEC_HISTORY,
    },
    "observer": {
        PERM_LIBRARY_VIEW, PERM_HISTORY_VIEW,
        SEC_HISTORY, SEC_REPORTS, SEC_LIBRARIES,
    },
}


def _hash_password(password: str, salt: Optional[str] = None) -> tuple:
    if salt is None:
        salt = secrets.token_hex(16)
    h = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    return h, salt


@dataclass
class User:
    id: str
    username: str
    password_hash: str
    salt: str
    full_name: str
    role: str
    permissions: Set[str] = field(default_factory=set)
    active: bool = True
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    created_by: str = ""

    def has(self, perm: str) -> bool:
        if not self.active:
            return False
        if self.role in ("developer", "admin"):
            return True
        return perm in self.permissions

    def check_password(self, password: str) -> bool:
        h, _ = _hash_password(password, self.salt)
        return h == self.password_hash


_USERS: Dict[str, User] = {}
_BY_USERNAME: Dict[str, str] = {}
_SESSIONS: Dict[str, str] = {}


def create_user(
    username: str,
    password: str,
    full_name: str,
    role: str,
    permissions: Optional[Set[str]] = None,
    created_by: str = "",
) -> User:
    username = username.lower().strip()
    if not username:
        raise ValueError("Username required")
    if username in _BY_USERNAME:
        raise ValueError("Username already exists")
    if role not in ROLES:
        raise ValueError("Invalid role")
    h, salt = _hash_password(password)
    perms = set(permissions) if permissions is not None else set(DEFAULT_PERMISSIONS.get(role, set()))
    user = User(
        id=str(uuid.uuid4()),
        username=username,
        password_hash=h,
        salt=salt,
        full_name=full_name.strip() or username,
        role=role,
        permissions=perms,
        created_by=created_by,
    )
    _USERS[user.id] = user
    _BY_USERNAME[user.username] = user.id
    return user


def get_user(user_id: str) -> Optional[User]:
    return _USERS.get(user_id)


def get_user_by_username(username: str) -> Optional[User]:
    uid = _BY_USERNAME.get(username.lower().strip())
    return _USERS.get(uid) if uid else None


def list_users() -> List[User]:
    return sorted(_USERS.values(), key=lambda u: (u.role, u.username))


def update_user(user_id: str, **kwargs) -> Optional[User]:
    user = _USERS.get(user_id)
    if not user:
        return None
    if "password" in kwargs and kwargs["password"]:
        h, salt = _hash_password(kwargs.pop("password"))
        user.password_hash = h
        user.salt = salt
    if "permissions" in kwargs and kwargs["permissions"] is not None:
        user.permissions = set(kwargs.pop("permissions"))
    for k, v in kwargs.items():
        if hasattr(user, k) and k not in ("id", "password_hash", "salt"):
            setattr(user, k, v)
    if "username" in kwargs:
        _BY_USERNAME.clear()
        for u in _USERS.values():
            _BY_USERNAME[u.username] = u.id
    return user


def delete_user(user_id: str) -> bool:
    user = _USERS.get(user_id)
    if not user:
        return False
    if user.role == "developer":
        devs = [u for u in _USERS.values() if u.role == "developer" and u.id != user_id]
        if not devs:
            raise ValueError("Cannot delete the last developer account")
    _BY_USERNAME.pop(user.username, None)
    del _USERS[user_id]
    to_del = [t for t, uid in _SESSIONS.items() if uid == user_id]
    for t in to_del:
        del _SESSIONS[t]
    return True


def authenticate(username: str, password: str) -> Optional[User]:
    user = get_user_by_username(username)
    if not user or not user.active:
        return None
    if not user.check_password(password):
        return None
    return user


def create_session_token(user_id: str) -> str:
    token = secrets.token_hex(32)
    _SESSIONS[token] = user_id
    return token


def get_user_by_token(token: Optional[str]) -> Optional[User]:
    if not token:
        return None
    uid = _SESSIONS.get(token)
    if not uid:
        return None
    return _USERS.get(uid)


def destroy_session(token: str) -> None:
    _SESSIONS.pop(token, None)


def seed_users() -> None:
    if _USERS:
        return
    create_user("developer", "DosePro@2026", "System Developer", "developer", created_by="system")
    create_user("admin", "Admin@2026", "System Administrator", "admin", created_by="system")
    create_user("physicist", "Physics@2026", "Medical Physicist", "physicist", created_by="system")
