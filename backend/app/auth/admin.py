"""Administrator operations. The API layer only lets administrators reach these; every one validates its input,
protects against locking everyone out (self-changes, last administrator) and writes an audit-log entry."""
from __future__ import annotations

import json

from app.auth import content, passwords, service
from app.auth.service import ROLES, audit
from app.auth.store import get_store
from app.engines.errors import ValidationError
from app.engines.learn import quiz as quiz_engine
from app.engines.learn.content import MODULES, TOPICS

MOD_IDS = [m for m, _ in MODULES]
LEVELS = quiz_engine.LEVELS
USER_COLS = "id,email,username,role,is_active,created_at,last_login_at"


def _esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


# ---------------- users ----------------
def list_users(search: str | None = None, role: str | None = None, active: bool | None = None, limit: int = 25, offset: int = 0) -> dict:
    if not isinstance(limit, int) or not 1 <= limit <= 100 or not isinstance(offset, int) or offset < 0:
        raise ValidationError("limit must be 1-100 and offset >= 0")
    where, params = [], []
    if search:
        where.append("(email LIKE ? ESCAPE '\\' OR username LIKE ? ESCAPE '\\')")
        params += [f"%{_esc(search[:64])}%"] * 2
    if role:
        if role not in ROLES:
            raise ValidationError("Unknown role")
        where.append("role=?")
        params.append(role)
    if active is not None:
        where.append("is_active=?")
        params.append(1 if active else 0)
    w = (" WHERE " + " AND ".join(where)) if where else ""
    st = get_store()
    items = st.all(f"SELECT {USER_COLS} FROM users{w} ORDER BY created_at DESC, id LIMIT ? OFFSET ?", tuple(params) + (limit, offset))
    return {"items": [dict(i, is_active=bool(i["is_active"])) for i in items], "total": st.scalar(f"SELECT COUNT(*) FROM users{w}", tuple(params)), "limit": limit, "offset": offset}


def _target(user_id: str) -> dict:
    u = service.get_user(user_id) if isinstance(user_id, str) else None
    if not u:
        raise ValidationError("User not found")
    return u


def _last_admin(u: dict) -> bool:
    return u["role"] == "administrator" and u["is_active"] and get_store().scalar("SELECT COUNT(*) FROM users WHERE role='administrator' AND is_active=1") <= 1


def update_user(actor: dict, user_id: str, is_active: bool | None = None, role: str | None = None, ip: str | None = None) -> dict:
    u = _target(user_id)
    if is_active is None and role is None:
        raise ValidationError("Nothing to change")
    if u["id"] == actor["id"]:
        raise ValidationError("You cannot change your own role or status")
    if role is not None and role not in ROLES:
        raise ValidationError("Unknown role")
    if is_active is not None and not isinstance(is_active, bool):
        raise ValidationError("is_active must be true or false")
    removing = (role == "student" and u["role"] == "administrator") or is_active is False
    if removing and _last_admin(u):
        raise ValidationError("Cannot remove the last active administrator")
    st, change = get_store(), {}
    if role is not None and role != u["role"]:
        st.run("UPDATE users SET role=? WHERE id=?", (role, u["id"]))
        change["role"] = [u["role"], role]
    if is_active is not None and bool(u["is_active"]) != is_active:
        st.run("UPDATE users SET is_active=? WHERE id=?", (1 if is_active else 0, u["id"]))
        change["is_active"] = [bool(u["is_active"]), is_active]
        if not is_active:
            service.revoke_all(u["id"])
    if change:
        audit(actor, "admin.user_update", target=u["username"], detail=change, ip=ip)
    return service.public(service.get_user(u["id"]))


def reset_password(actor: dict, user_id: str, new_password: str, ip: str | None = None) -> None:
    u = _target(user_id)
    h = passwords.hash_password(new_password)
    get_store().run("UPDATE users SET password_hash=?, failed_logins=0, locked_until=NULL WHERE id=?", (h, u["id"]))
    service.revoke_all(u["id"])
    audit(actor, "admin.password_reset", target=u["username"], ip=ip)


def delete_user(actor: dict, user_id: str, ip: str | None = None) -> None:
    u = _target(user_id)
    if u["id"] == actor["id"]:
        raise ValidationError("You cannot delete your own account")
    if _last_admin(u):
        raise ValidationError("Cannot delete the last active administrator")
    get_store().run("DELETE FROM users WHERE id=?", (u["id"],))
    audit(actor, "admin.user_delete", target=u["username"], ip=ip)


# ---------------- analytics ----------------
def performance() -> dict:
    st = get_store()
    students = st.all("SELECT id,username,email,last_login_at FROM users WHERE role='student' ORDER BY username")
    sid = {s["id"] for s in students}
    tmap = {t["id"]: t["module"] for t in content.topics()}
    att = {r["user_id"]: r for r in st.all("SELECT user_id, COUNT(*) n, AVG(percent) avg, MAX(percent) best FROM quiz_attempts WHERE user_id IS NOT NULL GROUP BY user_id")}
    prog = [r for r in st.all("SELECT user_id, topic_id FROM progress") if r["user_id"] in sid and r["topic_id"] in tmap]
    done: dict[str, int] = {}
    for r in prog:
        done[r["user_id"]] = done.get(r["user_id"], 0) + 1
    rows = [{"username": s["username"], "email": s["email"], "quiz_attempts": att.get(s["id"], {}).get("n", 0), "avg_percent": round(att[s["id"]]["avg"], 1) if s["id"] in att else None,
             "best_percent": att[s["id"]]["best"] if s["id"] in att else None, "topics_completed": done.get(s["id"], 0), "last_login_at": s["last_login_at"]} for s in students]
    qm = {r["module"]: r for r in st.all("SELECT module, COUNT(*) n, AVG(percent) avg FROM quiz_attempts GROUP BY module")}
    modules = []
    for mid, name in MODULES:
        topics = sum(1 for m in tmap.values() if m == mid)
        completed = sum(1 for r in prog if tmap[r["topic_id"]] == mid)
        denom = len(students) * topics
        modules.append({"module": mid, "name": name, "topics": topics, "topics_completed": completed, "students_started": len({r["user_id"] for r in prog if tmap[r["topic_id"]] == mid}),
                        "completion_percent": round(100 * completed / denom, 1) if denom else 0.0, "quiz_attempts": qm.get(mid, {}).get("n", 0),
                        "avg_quiz_percent": round(qm[mid]["avg"], 1) if mid in qm else None})
    total_den = len(students) * len(tmap)
    return {"students": rows, "modules": modules, "overall_completion_percent": round(100 * len(prog) / total_den, 1) if total_den else 0.0}


def stats() -> dict:
    st, now = get_store(), service.clock()
    u = st.one("SELECT COUNT(*) total, COALESCE(SUM(role='student'),0) students, COALESCE(SUM(role='administrator'),0) admins, COALESCE(SUM(is_active=1),0) active, COALESCE(SUM(is_active=0),0) inactive FROM users")
    perf = performance()
    attempts = st.scalar("SELECT COUNT(*) FROM quiz_attempts")
    return {"total_users": u["total"], "students": u["students"], "administrators": u["admins"], "active_accounts": u["active"], "inactive_accounts": u["inactive"],
            "simulations_total": st.scalar("SELECT COUNT(*) FROM usage_events"),
            "most_used_modules": st.all("SELECT module, COUNT(*) count FROM usage_events GROUP BY module ORDER BY count DESC, module LIMIT 10"),
            "simulations_per_day": st.all("SELECT date(ts,'unixepoch') day, COUNT(*) count FROM usage_events WHERE ts>=? GROUP BY day ORDER BY day", (now - 14 * 86400,)),
            "quiz_attempts": attempts, "quiz_participants": st.scalar("SELECT COUNT(DISTINCT user_id) FROM quiz_attempts WHERE user_id IS NOT NULL"),
            "quiz_average_percent": round(st.scalar("SELECT AVG(percent) FROM quiz_attempts", default=0.0), 1) if attempts else None,
            "learning_completion_percent": perf["overall_completion_percent"]}


def audit_list(limit: int = 100, action: str | None = None) -> list[dict]:
    if not isinstance(limit, int) or not 1 <= limit <= 500:
        raise ValidationError("limit must be 1-500")
    if action:
        rows = get_store().all("SELECT * FROM audit_logs WHERE action LIKE ? ESCAPE '\\' ORDER BY id DESC LIMIT ?", (f"{_esc(action[:40])}%", limit))
    else:
        rows = get_store().all("SELECT * FROM audit_logs ORDER BY id DESC LIMIT ?", (limit,))
    return [dict(r, detail=json.loads(r["detail"]) if r["detail"] else None) for r in rows]


# ---------------- content: lessons ----------------
def _text(d: dict, key: str, lo: int, hi: int) -> str:
    v = d.get(key)
    if not isinstance(v, str) or not lo <= len(v.strip()) <= hi:
        raise ValidationError(f"{key} must be {lo}-{hi} characters")
    return v.strip()


def _common(d: dict) -> tuple[str, str]:
    if d.get("module") not in MOD_IDS:
        raise ValidationError("Unknown module")
    if d.get("level") not in LEVELS:
        raise ValidationError("level must be beginner, intermediate or advanced")
    return d["module"], d["level"]


def _topic_fields(d: dict) -> tuple:
    module, level = _common(d)
    pts = d.get("points")
    if not isinstance(pts, list) or not 1 <= len(pts) <= 10 or any(not isinstance(p, str) or not 1 <= len(p.strip()) <= 300 for p in pts):
        raise ValidationError("points must be 1-10 short texts")
    return (module, level, _text(d, "title", 3, 150), _text(d, "summary", 10, 2000), json.dumps([p.strip() for p in pts]),
            _text(d, "example", 1, 1500), _text(d, "exercise", 1, 1500), _text(d, "answer", 1, 1500), 1 if d.get("published", True) else 0)


def list_topics() -> list[dict]:
    hid = {r["ref"] for r in get_store().all("SELECT ref FROM hidden_items WHERE kind='topic'")}
    out = [{"id": t["id"], "module": t["module"], "level": t["level"], "title": t["title"], "source": "built-in", "published": t["id"] not in hid} for t in TOPICS]
    for r in get_store().all("SELECT * FROM custom_topics ORDER BY id"):
        out.append({k: content.custom_topic(r)[k] for k in ("id", "module", "level", "title", "source", "published")})
    return out


def get_topic_admin(topic_id: str) -> dict:
    if topic_id.startswith("c-") and topic_id[2:].isdigit():
        r = get_store().one("SELECT * FROM custom_topics WHERE id=?", (int(topic_id[2:]),))
        if r:
            return content.custom_topic(r)
    t = next((t for t in TOPICS if t["id"] == topic_id), None)
    if not t:
        raise ValidationError("Topic not found")
    return dict(t, source="built-in")


def create_topic(actor: dict, d: dict, ip: str | None = None) -> dict:
    f = _topic_fields(d)
    now = service.clock()
    tid = get_store().run("INSERT INTO custom_topics(module,level,title,summary,points,example,exercise,answer,published,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)", f + (now, now))
    audit(actor, "admin.topic_create", target=f"c-{tid}", detail={"title": f[2]}, ip=ip)
    return get_topic_admin(f"c-{tid}")


def update_topic(actor: dict, topic_id: str, d: dict, ip: str | None = None) -> dict:
    if not (topic_id.startswith("c-") and topic_id[2:].isdigit()) or not get_store().one("SELECT id FROM custom_topics WHERE id=?", (int(topic_id[2:]),)):
        raise ValidationError("Only lessons created by an administrator can be edited (built-in lessons can be hidden instead)")
    f = _topic_fields(d)
    get_store().run("UPDATE custom_topics SET module=?,level=?,title=?,summary=?,points=?,example=?,exercise=?,answer=?,published=?,updated_at=? WHERE id=?", f + (service.clock(), int(topic_id[2:])))
    audit(actor, "admin.topic_update", target=topic_id, detail={"title": f[2]}, ip=ip)
    return get_topic_admin(topic_id)


def delete_topic(actor: dict, topic_id: str, ip: str | None = None) -> None:
    if not (topic_id.startswith("c-") and topic_id[2:].isdigit()) or not get_store().one("SELECT id FROM custom_topics WHERE id=?", (int(topic_id[2:]),)):
        raise ValidationError("Only lessons created by an administrator can be deleted (built-in lessons can be hidden instead)")
    get_store().batch([("DELETE FROM custom_topics WHERE id=?", (int(topic_id[2:]),)), ("DELETE FROM progress WHERE topic_id=?", (topic_id,))])
    audit(actor, "admin.topic_delete", target=topic_id, ip=ip)


def set_topic_published(actor: dict, topic_id: str, published: bool, ip: str | None = None) -> None:
    st = get_store()
    if topic_id.startswith("c-") and topic_id[2:].isdigit():
        if not st.one("SELECT id FROM custom_topics WHERE id=?", (int(topic_id[2:]),)):
            raise ValidationError("Topic not found")
        st.run("UPDATE custom_topics SET published=?, updated_at=? WHERE id=?", (1 if published else 0, service.clock(), int(topic_id[2:])))
    elif any(t["id"] == topic_id for t in TOPICS):
        st.run("DELETE FROM hidden_items WHERE kind='topic' AND ref=?", (topic_id,)) if published else st.run("INSERT OR IGNORE INTO hidden_items(kind,ref) VALUES('topic',?)", (topic_id,))
    else:
        raise ValidationError("Topic not found")
    audit(actor, "admin.topic_publish" if published else "admin.topic_unpublish", target=topic_id, ip=ip)


# ---------------- content: quiz questions ----------------
def _question_fields(d: dict) -> tuple:
    module, level = _common(d)
    opts = d.get("options")
    if not isinstance(opts, list) or not 2 <= len(opts) <= 6 or any(not isinstance(o, str) or not 1 <= len(o.strip()) <= 200 for o in opts):
        raise ValidationError("Provide 2-6 answer options (each up to 200 characters)")
    ci = d.get("correct_index")
    if isinstance(ci, bool) or not isinstance(ci, int) or not 0 <= ci < len(opts):
        raise ValidationError("correct_index must point at one of the options")
    return (module, level, _text(d, "prompt", 5, 600), json.dumps([o.strip() for o in opts]), ci, _text(d, "explanation", 1, 600), 1 if d.get("published", True) else 0)


def _cq(r: dict) -> dict:
    return {"id": f"c|{r['id']}", "module": r["module"], "level": r["level"], "prompt": r["prompt"], "options": json.loads(r["options"]),
            "correct_index": r["correct_index"], "explanation": r["explanation"], "source": "custom", "published": bool(r["published"])}


def list_questions() -> list[dict]:
    hid = {r["ref"] for r in get_store().all("SELECT ref FROM hidden_items WHERE kind='question'")}
    out = [{"id": f"m|{q[0]}|{i}", "module": q[0], "level": q[1], "prompt": q[2], "options": q[3], "correct_index": q[4], "explanation": q[5], "source": "built-in",
            "published": f"m|{q[0]}|{i}" not in hid} for i, q in enumerate(quiz_engine.MCQ)]
    return out + [_cq(r) for r in get_store().all("SELECT * FROM custom_questions ORDER BY id")]


def _cq_id(qid: str) -> int:
    if not (isinstance(qid, str) and qid.startswith("c|") and qid[2:].isdigit()) or not get_store().one("SELECT id FROM custom_questions WHERE id=?", (int(qid[2:]),)):
        raise ValidationError("Only questions created by an administrator can be edited or deleted (built-in questions can be hidden instead)")
    return int(qid[2:])


def create_question(actor: dict, d: dict, ip: str | None = None) -> dict:
    f = _question_fields(d)
    now = service.clock()
    qid = get_store().run("INSERT INTO custom_questions(module,level,prompt,options,correct_index,explanation,published,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)", f + (now, now))
    audit(actor, "admin.question_create", target=f"c|{qid}", ip=ip)
    return _cq(get_store().one("SELECT * FROM custom_questions WHERE id=?", (qid,)))


def update_question(actor: dict, qid: str, d: dict, ip: str | None = None) -> dict:
    n = _cq_id(qid)
    f = _question_fields(d)
    get_store().run("UPDATE custom_questions SET module=?,level=?,prompt=?,options=?,correct_index=?,explanation=?,published=?,updated_at=? WHERE id=?", f + (service.clock(), n))
    audit(actor, "admin.question_update", target=qid, ip=ip)
    return _cq(get_store().one("SELECT * FROM custom_questions WHERE id=?", (n,)))


def delete_question(actor: dict, qid: str, ip: str | None = None) -> None:
    get_store().run("DELETE FROM custom_questions WHERE id=?", (_cq_id(qid),))
    audit(actor, "admin.question_delete", target=qid, ip=ip)


def set_question_published(actor: dict, qid: str, published: bool, ip: str | None = None) -> None:
    st = get_store()
    if isinstance(qid, str) and qid.startswith("c|"):
        st.run("UPDATE custom_questions SET published=?, updated_at=? WHERE id=?", (1 if published else 0, service.clock(), _cq_id(qid)))
    elif any(f"m|{q[0]}|{i}" == qid for i, q in enumerate(quiz_engine.MCQ)):
        st.run("DELETE FROM hidden_items WHERE kind='question' AND ref=?", (qid,)) if published else st.run("INSERT OR IGNORE INTO hidden_items(kind,ref) VALUES('question',?)", (qid,))
    else:
        raise ValidationError("Question not found")
    audit(actor, "admin.question_publish" if published else "admin.question_unpublish", target=qid, ip=ip)
