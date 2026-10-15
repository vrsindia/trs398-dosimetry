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


# ---------------------------------------------------------------------------
# Roles & default permissions
# ---------------------------------------------------------------------------

ROLES = ("developer", "admin", "physicist", "intern", "observer")

# Permission keys
PERM_CALCULATE = "calculate"           # run absolute dosimetry sessions
PERM_TUNE = "tune"                     # tune output
PERM_LIBRARY_VIEW = "library_view"     # view detectors/linacs/tolerances
PERM_LIBRARY_EDIT = "library_edit"     # propose edits (goes to approval)
PERM_APPROVE = "approve"               # approve/reject library changes
PERM_USER_MANAGE = "user_manage"       # create/edit/delete users
PERM_DEPT_EDIT = "dept_edit"           # edit department details
PERM_HISTORY_VIEW = "history_view"
PERM_ADMIN_PANEL = "admin_panel"       # see user directory

DEFAULT_PERMISSIONS: Dict[str, Set[str]] = {
    "developer": {
        PERM_CALCULATE, PERM_TUNE, PERM_LIBRARY_VIEW, PERM_LIBRARY_EDIT,
        PERM_APPROVE, PERM_USER_MANAGE, PERM_DEPT_EDIT, PERM_HISTORY_VIEW,
        PERM_ADMIN_PANEL,
    },
    "admin": {
        PERM_CALCULATE, PERM_TUNE, PERM_LIBRARY_VIEW, PERM_LIBRARY_EDIT,
        PERM_APPROVE, PERM_USER_MANAGE, PERM_DEPT_EDIT, PERM_HISTORY_VIEW,
        PERM_ADMIN_PANEL,
    },
    "physicist": {
        PERM_CALCULATE, PERM_TUNE, PERM_LIBRARY_VIEW, PERM_LIBRARY_EDIT,
        PERM_APPROVE, PERM_DEPT_EDIT, PERM_HISTORY_VIEW,
    },
    "intern": {
        PERM_CALCULATE, PERM_LIBRARY_VIEW, PERM_HISTORY_VIEW,
        # no tune, no edit, no approve
    },
    "observer": {
        PERM_LIBRARY_VIEW, PERM_HISTORY_VIEW,
        # view only
    },
}


def _hash_password(password: str, salt: Optional[str] = None) -> tuple[str, str]:
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
    role: str                          # developer | admin | physicist | intern | observer
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


_USERS: Dict[str, User] = {}          # id -> User
_BY_USERNAME: Dict[str, str] = {}     # username -> id
_SESSIONS: Dict[str, str] = {}        # session_token -> user_id


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
        # rebuild index
        _BY_USERNAME.clear()
        for u in _USERS.values():
            _BY_USERNAME[u.username] = u.id
    return user


def delete_user(user_id: str) -> bool:
    user = _USERS.get(user_id)
    if not user:
        return False
    # prevent deleting last developer
    if user.role == "developer":
        devs = [u for u in _USERS.values() if u.role == "developer" and u.id != user_id]
        if not devs:
            raise ValueError("Cannot delete the last developer account")
    _BY_USERNAME.pop(user.username, None)
    del _USERS[user_id]
    # invalidate sessions
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
    """Create default developer and admin if empty."""
    if _USERS:
        return
    create_user("developer", "DosePro@2026", "System Developer", "developer", created_by="system")
    create_user("admin", "Admin@2026", "System Administrator", "admin", created_by="system")
    create_user("physicist", "Physics@2026", "Medical Physicist", "physicist", created_by="system")
