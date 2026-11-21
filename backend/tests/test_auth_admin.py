import contextlib
import json
try:
    import pytest
except ImportError:
    from tests._shim import pytest
from app.auth import admin, content, service, tokens
from app.auth.service import AuthError
from app.auth.store import Store, get_store, set_store
from app.engines.errors import ValidationError
from app.engines.learn import quiz as quiz_engine

PW = "Passw0rd-ok"


class Clock:
    t = 1_700_000_000.0
    def __call__(self): return self.t


@contextlib.contextmanager
def env():
    clk, old_clock, old_secret = Clock(), service.clock, service._SECRET
    set_store(Store()); service.clock = clk; service._SECRET = b"k" * 32; content.install()
    try:
        yield clk
    finally:
        service.clock, service._SECRET, quiz_engine.PROVIDER = old_clock, old_secret, None
        set_store(None)


def reg(name, role="student", pw=PW):
    return service.register(f"{name}@example.com", name, pw, role=role)


# ---------------- registration ----------------
def test_register_never_exposes_or_stores_plain_password():
    with env():
        u = reg("alice")
        assert set(u) == {"id", "email", "username", "role", "is_active", "created_at", "last_login_at"} and u["role"] == "student" and u["is_active"] is True
        stored = service.get_user(u["id"])["password_hash"]
        assert PW not in stored and len(stored) > 40

def test_register_validation_and_case_insensitive_uniqueness():
    with env():
        reg("alice")
        for args in [("bad", "bob", PW), ("b@x.co", "a", PW), ("b@x.co", "bob smith", PW), ("b@x.co", "bob", "short1"), ("b@x.co", "bob", "nodigitsatall"),
                     ("ALICE@example.com", "bob", PW), ("b@x.co", "ALICE", PW)]:
            with pytest.raises(ValidationError):
                service.register(*args)
        with pytest.raises(ValidationError):
            service.register("b@x.co", "bob", PW, role="root")

# ---------------- login ----------------
def test_login_by_email_or_username_and_generic_failure_message():
    with env():
        reg("alice")
        for ident in ("alice", "ALICE@example.com"):
            user, access, refresh = service.login(ident, PW)
            assert user["username"] == "alice" and access.count(".") == 2 and len(refresh) > 40
        msgs = set()
        for ident, pw in [("alice", "wrong-Pass1"), ("nobody", PW), ("' OR '1'='1", "x"), ("", PW)]:
            with pytest.raises(AuthError) as e:
                service.login(ident, pw)
            msgs.add(str(e.value))
        assert msgs == {"Invalid credentials"}                      # unknown user and wrong password look identical

def test_account_locks_after_five_failures_and_unlocks_later():
    with env() as clk:
        reg("alice")
        for _ in range(5):
            with pytest.raises(AuthError):
                service.login("alice", "bad-Pass1")
        with pytest.raises(AuthError, match="Too many"):
            service.login("alice", PW)                               # even the right password is refused while locked
        clk.t += service.LOCK_SECONDS - 1
        with pytest.raises(AuthError, match="Too many"):
            service.login("alice", PW)
        clk.t += 2
        assert service.login("alice", PW)[0]["username"] == "alice"
        assert any(a["action"] == "auth.account_locked" for a in admin.audit_list())

def test_success_resets_failure_counter_and_disabled_accounts_cannot_login():
    with env():
        u = reg("alice")
        for _ in range(4):
            with pytest.raises(AuthError):
                service.login("alice", "bad-Pass1")
        service.login("alice", PW)
        for _ in range(4):
            with pytest.raises(AuthError):
                service.login("alice", "bad-Pass1")
        service.login("alice", PW)                                   # counter was reset, so still not locked
        a = reg("boss", "administrator")
        admin.update_user(a, u["id"], is_active=False)
        with pytest.raises(AuthError, match="disabled"):
            service.login("alice", PW)

# ---------------- tokens & sessions ----------------
def test_access_token_resolves_user_and_role_change_applies_immediately():
    with env():
        a, u = reg("boss", "administrator"), reg("alice")
        _, access, _ = service.login("alice", PW)
        assert service.user_from_access(access)["role"] == "student"
        admin.update_user(a, u["id"], role="administrator")
        assert service.user_from_access(access)["role"] == "administrator"     # role is read from the database, not from the token
        admin.update_user(a, u["id"], is_active=False)
        with pytest.raises(AuthError):
            service.user_from_access(access)                                   # deactivation also kills a still-valid token

def test_expired_forged_and_wrong_type_tokens_are_rejected():
    with env() as clk:
        reg("alice")
        _, access, _ = service.login("alice", PW)
        clk.t += tokens.ACCESS_TTL + 1
        with pytest.raises(AuthError):
            service.user_from_access(access)
        forged = tokens.encode({"sub": "x", "exp": clk.t + 999, "typ": "access"}, b"attacker" * 4)
        with pytest.raises(AuthError):
            service.user_from_access(forged)
        user_id = get_store().one("SELECT id FROM users")["id"]
        refresh_type = tokens.encode({"sub": user_id, "exp": clk.t + 999, "typ": "refresh"}, service.secret())
        with pytest.raises(AuthError, match="Wrong token type"):
            service.user_from_access(refresh_type)

def test_refresh_rotates_and_late_reuse_revokes_every_session():
    with env() as clk:
        reg("alice")
        _, _, r1 = service.login("alice", PW)
        _, _, other = service.login("alice", PW)                     # a second device
        clk.t += 60
        u, access, r2 = service.refresh(r1)
        assert r2 != r1 and service.user_from_access(access)["username"] == "alice"
        clk.t += service.REUSE_GRACE + 1
        with pytest.raises(AuthError):
            service.refresh(r1)                                      # the old token resurfaces later = theft signal
        for token in (r2, other):
            with pytest.raises(AuthError):
                service.refresh(token)                               # ...so ALL sessions are gone
        assert any(a["action"] == "auth.refresh_reuse_detected" for a in admin.audit_list())

def test_concurrent_refresh_race_does_not_log_the_user_out():
    with env() as clk:
        reg("alice")
        _, _, r1 = service.login("alice", PW)
        clk.t += 60
        _, _, r2 = service.refresh(r1)                               # tab A wins the race
        clk.t += 2
        with pytest.raises(AuthError):
            service.refresh(r1)                                      # tab B used the same cookie 2 s later: refused...
        assert service.refresh(r2)[0]["username"] == "alice"         # ...but tab A's new session is still valid
        assert not any(a["action"] == "auth.refresh_reuse_detected" for a in admin.audit_list())

def test_logout_revokes_and_refresh_expires():
    with env() as clk:
        reg("alice")
        _, _, r = service.login("alice", PW)
        service.logout(r)
        with pytest.raises(AuthError):
            service.refresh(r)
        _, _, r = service.login("alice", PW)
        clk.t += tokens.REFRESH_TTL + 1
        with pytest.raises(AuthError, match="expired"):
            service.refresh(r)
        for junk in ("", "nonsense", None):
            with pytest.raises(AuthError):
                service.refresh(junk)

def test_only_hashes_of_refresh_tokens_are_stored():
    with env():
        reg("alice")
        _, _, raw = service.login("alice", PW)
        rows = get_store().all("SELECT token_hash FROM refresh_tokens")
        assert rows and all(r["token_hash"] != raw and len(r["token_hash"]) == 64 for r in rows)

# ---------------- admin: users ----------------
def test_admin_cannot_lock_everyone_out():
    with env():
        a = reg("boss", "administrator")
        for call in (lambda: admin.update_user(a, a["id"], role="student"), lambda: admin.update_user(a, a["id"], is_active=False), lambda: admin.delete_user(a, a["id"])):
            with pytest.raises(ValidationError):
                call()
        b = reg("boss2", "administrator")
        assert admin.update_user(a, b["id"], role="student")["role"] == "student"      # allowed: boss is still an admin

def test_last_administrator_is_protected_from_other_admins_too():
    with env():
        a, b = reg("boss", "administrator"), reg("boss2", "administrator")
        admin.update_user(a, b["id"], is_active=False)               # boss2 disabled -> boss is the only ACTIVE admin
        spare = {"id": "someone-else", "username": "ghost"}
        with pytest.raises(ValidationError, match="last active administrator"):
            admin.update_user(spare, a["id"], role="student")
        with pytest.raises(ValidationError, match="last active administrator"):
            admin.delete_user(spare, a["id"])

def test_reset_password_revokes_sessions_and_old_password_stops_working():
    with env():
        a, u = reg("boss", "administrator"), reg("alice")
        _, _, r = service.login("alice", PW)
        admin.reset_password(a, u["id"], "Brand-new9pass")
        with pytest.raises(AuthError):
            service.refresh(r)
        with pytest.raises(AuthError):
            service.login("alice", PW)
        assert service.login("alice", "Brand-new9pass")[0]["username"] == "alice"
        with pytest.raises(ValidationError):
            admin.reset_password(a, u["id"], "weak")

def test_delete_user_cascades_and_keeps_anonymous_stats():
    with env():
        a, u = reg("boss", "administrator"), reg("alice")
        service.set_progress(u["id"], "cpu-basics", True)
        service.record_quiz_attempt(u["id"], "cpu", "beginner", {"score": 2, "total": 3, "percent": 66.7, "by_level": {}})
        admin.delete_user(a, u["id"])
        st = get_store()
        assert st.scalar("SELECT COUNT(*) FROM progress") == 0 and st.scalar("SELECT COUNT(*) FROM quiz_attempts WHERE user_id IS NULL") == 1
        with pytest.raises(ValidationError):
            admin.delete_user(a, u["id"])

def test_user_search_filters_pagination_and_injection_safety():
    with env():
        reg("boss", "administrator")
        for n in ("alice", "alicia", "bob_x", "carol"):
            reg(n)
        assert {u["username"] for u in admin.list_users(search="ali")["items"]} == {"alice", "alicia"}
        assert admin.list_users(search="_")["total"] == 1             # "_" is escaped: matches only the literal underscore in bob_x
        assert admin.list_users(search="%")["total"] == 0
        for evil in ["' OR '1'='1", "'; DROP TABLE users;--", "\\", "alice' --"]:
            assert admin.list_users(search=evil)["total"] == 0
        assert admin.list_users()["total"] == 5 and admin.list_users(role="administrator")["total"] == 1
        page = admin.list_users(limit=2, offset=4)
        assert len(page["items"]) == 1 and page["total"] == 5
        for bad in [dict(limit=0), dict(limit=101), dict(offset=-1), dict(role="root")]:
            with pytest.raises(ValidationError):
                admin.list_users(**bad)
        assert all("password_hash" not in u for u in admin.list_users()["items"])

# ---------------- admin: analytics ----------------
def test_stats_and_performance_are_computed_from_real_records():
    with env() as clk:
        a = reg("boss", "administrator")
        stu1, stu2, stu3 = reg("stu1"), reg("stu2"), reg("stu3")
        admin.update_user(a, stu3["id"], is_active=False)
        for m, uid in [("cpu", stu1["id"]), ("cpu", None), ("paging", stu2["id"]), ("cpu", stu1["id"])]:
            service.record_usage(m, "simulate", uid)
        service.record_quiz_attempt(stu1["id"], "cpu", "beginner", {"score": 3, "total": 3, "percent": 100.0, "by_level": {}})
        service.record_quiz_attempt(stu1["id"], "cpu", "beginner", {"score": 1, "total": 3, "percent": 33.3, "by_level": {}})
        service.record_quiz_attempt(stu2["id"], "paging", "advanced", {"score": 2, "total": 3, "percent": 66.7, "by_level": {}})
        for t in ("cpu-basics", "cpu-rr"):
            service.set_progress(stu1["id"], t, True)
        service.set_progress(stu2["id"], "cpu-basics", True)
        service.set_progress(a["id"], "cpu-basics", True)             # admins do not count as students
        s = admin.stats()
        assert (s["total_users"], s["students"], s["administrators"], s["active_accounts"], s["inactive_accounts"]) == (4, 3, 1, 3, 1)
        assert s["simulations_total"] == 4 and s["most_used_modules"] == [{"module": "cpu", "count": 3}, {"module": "paging", "count": 1}]
        assert s["quiz_attempts"] == 3 and s["quiz_participants"] == 2 and s["quiz_average_percent"] == round((100 + 33.3 + 66.7) / 3, 1)
        assert sum(d["count"] for d in s["simulations_per_day"]) == 4
        perf = admin.performance()
        rows = {r["username"]: r for r in perf["students"]}
        assert rows["stu1"]["quiz_attempts"] == 2 and rows["stu1"]["avg_percent"] == round((100 + 33.3) / 2, 1) and rows["stu1"]["best_percent"] == 100.0 and rows["stu1"]["topics_completed"] == 2
        assert rows["stu3"]["quiz_attempts"] == 0 and rows["stu3"]["avg_percent"] is None
        cpu = next(m for m in perf["modules"] if m["module"] == "cpu")
        assert cpu["topics"] == 3 and cpu["topics_completed"] == 3 and cpu["students_started"] == 2 and cpu["completion_percent"] == round(100 * 3 / (3 * 3), 1)
        assert cpu["quiz_attempts"] == 2 and perf["overall_completion_percent"] == round(100 * 3 / (3 * 30), 1)

def test_empty_platform_has_sane_stats():
    with env():
        s = admin.stats()
        assert s["students"] == 0 and s["simulations_total"] == 0 and s["quiz_average_percent"] is None and s["learning_completion_percent"] == 0.0

# ---------------- admin: content ----------------
TOPIC = {"module": "cpu", "level": "beginner", "title": "My custom lesson", "summary": "A long enough summary here.", "points": ["one", "two"],
         "example": "ex", "exercise": "q?", "answer": "a", "published": True}
QUESTION = {"module": "cpu", "level": "beginner", "prompt": "What does CPU stand for?", "options": ["Central Processing Unit", "Computer Personal Unit", "Core Process Utility"],
            "correct_index": 0, "explanation": "Central Processing Unit.", "published": True}

def test_custom_lessons_are_visible_to_learners_only_when_published():
    with env():
        a = reg("boss", "administrator")
        t = admin.create_topic(a, TOPIC)
        assert t["id"].startswith("c-") and [x["id"] for x in content.topics("cpu")][-1] == t["id"]
        admin.set_topic_published(a, t["id"], False)
        assert t["id"] not in [x["id"] for x in content.topics()]
        admin.set_topic_published(a, t["id"], True)
        upd = admin.update_topic(a, t["id"], {**TOPIC, "title": "Renamed lesson"})
        assert upd["title"] == "Renamed lesson" and content.topic(t["id"])["title"] == "Renamed lesson"
        admin.delete_topic(a, t["id"])
        assert content.topic(t["id"]) is None

def test_builtin_lessons_can_be_hidden_but_not_edited_or_deleted():
    with env():
        a = reg("boss", "administrator")
        admin.set_topic_published(a, "cpu-basics", False)
        assert content.topic("cpu-basics") is None and next(t for t in admin.list_topics() if t["id"] == "cpu-basics")["published"] is False
        admin.set_topic_published(a, "cpu-basics", True)
        assert content.topic("cpu-basics")["source"] == "built-in"
        for call in (lambda: admin.update_topic(a, "cpu-basics", TOPIC), lambda: admin.delete_topic(a, "cpu-basics"), lambda: admin.set_topic_published(a, "nope", True)):
            with pytest.raises(ValidationError):
                call()

def test_progress_rejects_unknown_or_hidden_topics_and_is_idempotent():
    with env():
        a, u = reg("boss", "administrator"), reg("alice")
        assert service.set_progress(u["id"], "cpu-basics", True) == ["cpu-basics"] == service.set_progress(u["id"], "cpu-basics", True)
        with pytest.raises(ValidationError):
            service.set_progress(u["id"], "../../etc", True)
        admin.set_topic_published(a, "page-basics", False)
        with pytest.raises(ValidationError):
            service.set_progress(u["id"], "page-basics", True)
        assert service.set_progress(u["id"], "cpu-basics", False) == []

def test_custom_questions_flow_into_quizzes_and_are_graded_correctly():
    with env():
        a = reg("boss", "administrator")
        q = admin.create_question(a, QUESTION)
        built = quiz_engine.build("cpu", "beginner", seed=1)
        item = next(x for x in built if x["id"] == q["id"])
        assert item["options"] == QUESTION["options"] and "correct_index" not in item and "explanation" not in item
        ids = [x["id"] for x in built]
        good = quiz_engine.grade(ids, {q["id"]: "0"})
        bad = quiz_engine.grade(ids, {q["id"]: "1"})
        assert next(r for r in good["results"] if r["id"] == q["id"])["correct"] is True
        r = next(r for r in bad["results"] if r["id"] == q["id"])
        assert r["correct"] is False and r["correct_answer"] == "Central Processing Unit" and r["explanation"]
        admin.set_question_published(a, q["id"], False)
        assert q["id"] not in [x["id"] for x in quiz_engine.build("cpu", "beginner", seed=1)]

def test_hiding_a_builtin_question_removes_it_from_quizzes():
    with env():
        a = reg("boss", "administrator")
        before = [x["id"] for x in quiz_engine.build("disk", "all", seed=2) if x["type"] == "mcq"]
        assert len(before) == 3
        admin.set_question_published(a, before[0], False)
        after = [x["id"] for x in quiz_engine.build("disk", "all", seed=2) if x["type"] == "mcq"]
        assert after == before[1:]
        admin.set_question_published(a, before[0], True)
        assert [x["id"] for x in quiz_engine.build("disk", "all", seed=2) if x["type"] == "mcq"] == before

def test_content_validation():
    with env():
        a = reg("boss", "administrator")
        for bad in [{**TOPIC, "module": "nope"}, {**TOPIC, "level": "expert"}, {**TOPIC, "title": "ab"}, {**TOPIC, "points": []}, {**TOPIC, "points": ["x"] * 11}, {**TOPIC, "summary": "short"}, {**TOPIC, "answer": ""}]:
            with pytest.raises(ValidationError):
                admin.create_topic(a, bad)
        for bad in [{**QUESTION, "options": ["only one"]}, {**QUESTION, "correct_index": 3}, {**QUESTION, "correct_index": True}, {**QUESTION, "correct_index": -1},
                    {**QUESTION, "prompt": "hi"}, {**QUESTION, "options": ["a", ""]}, {**QUESTION, "module": "x"}]:
            with pytest.raises(ValidationError):
                admin.create_question(a, bad)
        with pytest.raises(ValidationError):
            admin.update_question(a, "m|cpu|0", QUESTION)               # built-ins are not editable
        with pytest.raises(ValidationError):
            quiz_engine.grade(["c|999999"], {})                          # unknown custom id

def test_every_admin_action_is_audited():
    with env():
        a, u = reg("boss", "administrator"), reg("alice")
        t, q = admin.create_topic(a, TOPIC), admin.create_question(a, QUESTION)
        admin.update_user(a, u["id"], role="administrator"); admin.update_user(a, u["id"], role="student")
        admin.reset_password(a, u["id"], "Another9pass"); admin.set_topic_published(a, t["id"], False); admin.set_question_published(a, q["id"], False)
        admin.delete_topic(a, t["id"]); admin.delete_question(a, q["id"]); admin.delete_user(a, u["id"])
        actions = [x["action"] for x in admin.audit_list(limit=200)]
        for expected in ["admin.topic_create", "admin.question_create", "admin.user_update", "admin.password_reset", "admin.topic_unpublish", "admin.question_unpublish",
                         "admin.topic_delete", "admin.question_delete", "admin.user_delete"]:
            assert expected in actions, expected
        assert actions.count("admin.user_update") == 2
        entry = next(x for x in admin.audit_list(limit=200) if x["action"] == "admin.user_update")
        assert entry["actor_name"] == "boss" and entry["target"] == "alice" and entry["detail"]
        assert [x["action"] for x in admin.audit_list(action="admin.topic")] and all(x["action"].startswith("admin.topic") for x in admin.audit_list(action="admin.topic"))
        with pytest.raises(ValidationError):
            admin.audit_list(limit=0)

def test_ensure_admin_only_creates_the_first_one():
    with env():
        assert service.ensure_admin("root@example.com", "root", PW) is True
        assert service.ensure_admin("root2@example.com", "root2", PW) is False
        assert get_store().scalar("SELECT COUNT(*) FROM users WHERE role='administrator'") == 1
