"""Accounts and sessions. Roles come from the DATABASE on every request (never trusted from the token), so a demotion or
deactivation takes effect immediately. Login uses one generic error for unknown user / wrong password and locks an
account for 15 minutes after 5 failures. Refresh tokens rotate on every use; reusing an old one revokes every session."""
from __future__ import annotations

import json
import re
import sqlite3
import time
import uuid

from app.auth import passwords, tokens
from app.auth.store import DATA_DIR, get_store
from app.engines.errors import ValidationError

clock = time.time
LOCK_AFTER, LOCK_SECONDS = 5, 15 * 60
REUSE_GRACE = 10          # seconds: two tabs / a double request may legitimately present the same just-rotated token
EMAIL = re.compile(r"^[A-Za-z0-9._%+-]{1,64}@[A-Za-z0-9.-]{1,190}\.[A-Za-z]{2,24}$")
USERNAME = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")
ROLES = ("student", "administrator")
_SECRET: bytes | None = None
_DUMMY: str | None = None


class AuthError(Exception):
    """401: not logged in / bad credentials / bad session."""


class Forbidden(Exception):
    """403: logged in but not allowed."""


def secret() -> bytes:
    global _SECRET
    if _SECRET is None:
        _SECRET = tokens.load_secret(DATA_DIR)
    return _SECRET


def _dummy_hash() -> str:
    global _DUMMY
    if _DUMMY is None:
        _DUMMY = passwords.hash_password("Dummy-password1")
    return _DUMMY


def public(u: dict) -> dict:
    return {k: u[k] for k in ("id", "email", "username", "role", "is_active", "created_at", "last_login_at")} | {"is_active": bool(u["is_active"])}


def audit(actor: dict | None, action: str, target: str | None = None, detail: dict | None = None, ip: str | None = None) -> None:
    get_store().run("INSERT INTO audit_logs(ts,actor_id,actor_name,action,target,detail,ip) VALUES(?,?,?,?,?,?,?)",
                    (clock(), actor["id"] if actor else None, actor["username"] if actor else None, action, target,
                     json.dumps(detail) if detail else None, ip))


def get_user(user_id: str) -> dict | None:
    return get_store().one("SELECT * FROM users WHERE id=?", (user_id,))


def register(email: str, username: str, password: str, role: str = "student", ip: str | None = None, actor: dict | None = None) -> dict:
    if not isinstance(email, str) or not EMAIL.match(email.strip()):
        raise ValidationError("Enter a valid email address")
    if not isinstance(username, str) or not USERNAME.match(username.strip()):
        raise ValidationError("Username must be 3-32 characters: letters, digits, '_', '-' or '.'")
    if role not in ROLES:
        raise ValidationError("Unknown role")
    h = passwords.hash_password(password)                    # also validates the password policy
    uid = uuid.uuid4().hex
    try:
        get_store().run("INSERT INTO users(id,email,username,password_hash,role,is_active,created_at) VALUES(?,?,?,?,?,1,?)",
                        (uid, email.strip(), username.strip(), h, role, clock()))
    except sqlite3.IntegrityError:
        raise ValidationError("That email or username is already registered")
    u = get_user(uid)
    audit(actor or u, "user.register" if role == "student" else "user.create_admin", target=u["username"], ip=ip)
    return public(u)


def _issue(user_id: str, now: float) -> tuple[str, str]:
    raw, h = tokens.new_refresh_token()
    get_store().run("INSERT INTO refresh_tokens(user_id,token_hash,expires_at,created_at) VALUES(?,?,?,?)", (user_id, h, now + tokens.REFRESH_TTL, now))
    return tokens.create_access_token(user_id, secret(), now=now), raw


def login(identifier: str, password: str, ip: str | None = None) -> tuple[dict, str, str]:
    st, now = get_store(), clock()
    if not isinstance(identifier, str) or not isinstance(password, str) or not identifier.strip() or len(identifier) > 254 or len(password) > 128:
        raise AuthError("Invalid credentials")
    ident = identifier.strip()
    u = st.one("SELECT * FROM users WHERE email=? OR username=?", (ident, ident))
    if u and u["locked_until"] and u["locked_until"] > now:
        audit(u, "auth.login_blocked", ip=ip)
        raise AuthError("Too many failed attempts. Try again in a few minutes.")
    ok = passwords.verify_password(u["password_hash"] if u else _dummy_hash(), password)      # same work for unknown users
    if not u or not ok:
        if u:
            failed = u["failed_logins"] + 1
            lock = now + LOCK_SECONDS if failed >= LOCK_AFTER else None
            st.run("UPDATE users SET failed_logins=?, locked_until=? WHERE id=?", (0 if lock else failed, lock, u["id"]))
            if lock:
                audit(u, "auth.account_locked", ip=ip)
        audit(None, "auth.login_failed", target=ident[:64], ip=ip)
        raise AuthError("Invalid credentials")
    if not u["is_active"]:
        audit(u, "auth.login_disabled", ip=ip)
        raise AuthError("This account has been disabled. Contact an administrator.")
    st.run("UPDATE users SET failed_logins=0, locked_until=NULL, last_login_at=? WHERE id=?", (now, u["id"]))
    access, refresh = _issue(u["id"], now)
    audit(u, "auth.login", ip=ip)
    return public(get_user(u["id"])), access, refresh


def refresh(raw: str, ip: str | None = None) -> tuple[dict, str, str]:
    st, now = get_store(), clock()
    if not isinstance(raw, str) or not raw:
        raise AuthError("Not signed in")
    row = st.one("SELECT * FROM refresh_tokens WHERE token_hash=?", (tokens.hash_token(raw),))
    if not row:
        raise AuthError("Session not valid")
    if row["revoked_at"]:
        if now - row["revoked_at"] <= REUSE_GRACE:           # a concurrent request raced the rotation: refuse, but do not punish
            raise AuthError("Session not valid")
        # an old, already-used token came back later: assume it was stolen and end every session of this user
        st.run("UPDATE refresh_tokens SET revoked_at=? WHERE user_id=? AND revoked_at IS NULL", (now, row["user_id"]))
        audit(get_user(row["user_id"]), "auth.refresh_reuse_detected", ip=ip)
        raise AuthError("Session not valid")
    u = get_user(row["user_id"])
    if row["expires_at"] <= now or not u or not u["is_active"]:
        raise AuthError("Session expired")
    new_raw, new_hash = tokens.new_refresh_token()
    st.batch([("UPDATE refresh_tokens SET revoked_at=? WHERE id=?", (now, row["id"])),
              ("INSERT INTO refresh_tokens(user_id,token_hash,expires_at,created_at) VALUES(?,?,?,?)", (u["id"], new_hash, now + tokens.REFRESH_TTL, now))])
    return public(u), tokens.create_access_token(u["id"], secret(), now=now), new_raw


def logout(raw: str | None, ip: str | None = None) -> None:
    if not raw:
        return
    row = get_store().one("SELECT * FROM refresh_tokens WHERE token_hash=?", (tokens.hash_token(raw),))
    if row and not row["revoked_at"]:
        get_store().run("UPDATE refresh_tokens SET revoked_at=? WHERE id=?", (clock(), row["id"]))
        audit(get_user(row["user_id"]), "auth.logout", ip=ip)


def user_from_access(token: str) -> dict:
    try:
        p = tokens.decode(token, secret(), now=clock())
    except tokens.TokenError as e:
        raise AuthError(str(e))
    if p.get("typ") != "access":
        raise AuthError("Wrong token type")
    u = get_user(p.get("sub", ""))
    if not u or not u["is_active"]:
        raise AuthError("Account not available")
    return public(u)


def revoke_all(user_id: str) -> None:
    get_store().run("UPDATE refresh_tokens SET revoked_at=? WHERE user_id=? AND revoked_at IS NULL", (clock(), user_id))


def ensure_admin(email: str, username: str, password: str) -> bool:
    """Create the first administrator if none exists. Returns True if one was created."""
    if get_store().scalar("SELECT COUNT(*) FROM users WHERE role='administrator'"):
        return False
    register(email, username, password, role="administrator")
    return True


# ---------- per-user data ----------
def record_usage(module: str, action: str, user_id: str | None) -> None:
    get_store().run("INSERT INTO usage_events(ts,user_id,module,action) VALUES(?,?,?,?)", (clock(), user_id, module, action))


def record_quiz_attempt(user_id: str | None, module: str, level: str, graded: dict) -> None:
    get_store().run("INSERT INTO quiz_attempts(ts,user_id,module,level,score,total,percent,by_level) VALUES(?,?,?,?,?,?,?,?)",
                    (clock(), user_id, module, level, graded["score"], graded["total"], graded["percent"], json.dumps(graded["by_level"])))


def quiz_history(user_id: str, limit: int = 50) -> list[dict]:
    return get_store().all("SELECT ts,module,level,score,total,percent FROM quiz_attempts WHERE user_id=? ORDER BY ts DESC, id DESC LIMIT ?", (user_id, limit))


def get_progress(user_id: str) -> list[str]:
    return [r["topic_id"] for r in get_store().all("SELECT topic_id FROM progress WHERE user_id=? ORDER BY completed_at", (user_id,))]


def set_progress(user_id: str, topic_id: str, completed: bool) -> list[str]:
    from app.auth import content
    if not any(t["id"] == topic_id for t in content.topics()):
        raise ValidationError("Unknown topic")
    if completed:
        get_store().run("INSERT OR IGNORE INTO progress(user_id,topic_id,completed_at) VALUES(?,?,?)", (user_id, topic_id, clock()))
    else:
        get_store().run("DELETE FROM progress WHERE user_id=? AND topic_id=?", (user_id, topic_id))
    return get_progress(user_id)
