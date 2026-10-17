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

# Permission keys
PERM_CALCULATE = "calculate"
PERM_TUNE = "tune"
PERM_LIBRARY_VIEW = "library_view"
PERM_LIBRARY_EDIT = "library_edit"
PERM_APPROVE = "approve"
PERM_USER_MANAGE = "user_manage"
PERM_DEPT_EDIT = "dept_edit"
PERM_HISTORY_VIEW = "history_view"
PERM_ADMIN_PANEL = "admin_panel"

# Section visibility (admin/developer assign per user)
SEC_LINAC = "sec_linac"
SEC_BRACHY = "sec_brachy"
SEC_ACTIVITY = "sec_activity"
SEC_BED = "sec_bed"
SEC_BED_COMBINED = "sec_bed_combined"
SEC_GAP = "sec_gap"
SEC_LIBRARIES = "sec_libraries"
SEC_HISTORY = "sec_history"
SEC_REPORTS = "sec_reports"
SEC_APPROVALS = "sec_approvals"
SEC_DEPARTMENT = "sec_department"

SECTION_LABELS = {
    SEC_LINAC: "Linac absolute dosimetry",
    SEC_BRACHY: "Brachytherapy",
    SEC_ACTIVITY: "Source activity calculator",
    SEC_BED: "Bed / eqd2 calculator",
    SEC_BED_COMBINED: "Ebrt + brachy bed",
    SEC_GAP: "Gap correction",
    SEC_LIBRARIES: "Libraries (detectors, machines, tolerances)",
    SEC_HISTORY: "Output history",
    SEC_REPORTS: "Reports",
    SEC_APPROVALS: "Approvals",
    SEC_DEPARTMENT: "Department",
}

ALL_SECTION_PERMS = list(SECTION_LABELS.keys())

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
        PERM_APPROVE, PERM_DEPT_EDIT, PERM_HISTORY_VIEW,
        *ALL_SECTION_PERMS,
    },
    "doctor": {
        PERM_LIBRARY_VIEW, PERM_HISTORY_VIEW,
        SEC_BED, SEC_BED_COMBINED, SEC_GAP, SEC_REPORTS, SEC_DEPARTMENT,
    },
    "technologist": {
        PERM_CALCULATE, PERM_LIBRARY_VIEW, PERM_HISTORY_VIEW,
        SEC_LINAC, SEC_BRACHY, SEC_ACTIVITY, SEC_LIBRARIES, SEC_HISTORY, SEC_DEPARTMENT,
    },
    "intern": {
        PERM_CALCULATE, PERM_LIBRARY_VIEW, PERM_HISTORY_VIEW,
        SEC_LINAC, SEC_BRACHY, SEC_ACTIVITY, SEC_BED, SEC_BED_COMBINED, SEC_GAP,
        SEC_LIBRARIES, SEC_HISTORY, SEC_DEPARTMENT,
    },
    "observer": {
        PERM_LIBRARY_VIEW, PERM_HISTORY_VIEW,
        SEC_LIBRARIES, SEC_HISTORY, SEC_REPORTS, SEC_DEPARTMENT,
    },
}

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
    **SECTION_LABELS,
}


def _hash_password(password: str, salt: Optional[str] = None) -> tuple:
    if salt is None:
        salt = secrets.token_hex(16)
    h = hashlib.sha256((salt + password).encode()).hexdigest()
    return h, salt


def _new_id() -> str:
    return str(uuid.uuid4())[:8]


@dataclass
class User:
    id: str
    username: str
    full_name: str
    role: str
    password_hash: str
    salt: str
    active: bool = True
    permissions: Set[str] = field(default_factory=set)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    created_by: str = ""

    def has(self, perm: str) -> bool:
        return perm in self.permissions

    def check_password(self, password: str) -> bool:
        h, _ = _hash_password(password, self.salt)
        return h == self.password_hash


_USERS: Dict[str, User] = {}
_BY_USERNAME: Dict[str, str] = {}
_SESSIONS: Dict[str, str] = {}


def create_user(username: str, password: str, full_name: str, role: str,
                created_by: str = "", permissions: Optional[Set[str]] = None) -> User:
    if username.lower() in _BY_USERNAME:
        raise ValueError("Username already exists")
    if role not in ROLES:
        raise ValueError(f"Invalid role: {role}")
    h, salt = _hash_password(password)
    perms = permissions if permissions is not None else set(DEFAULT_PERMISSIONS.get(role, set()))
    user = User(
        id=_new_id(),
        username=username.lower().strip(),
        full_name=full_name,
        role=role,
        password_hash=h,
        salt=salt,
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
