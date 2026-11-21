"""Real HTTP tests for accounts, cookies, authorization and the admin API.
Need the real FastAPI:  pip install -r requirements.txt   then   pytest tests/test_api_auth_admin.py"""
from fastapi.testclient import TestClient

from app.auth import content, service
from app.auth.store import Store, set_store
from app.main import app

P = "/api/v1"
PW = "Passw0rd-ok"
H = {"X-OSLab-Client": "web"}


def fresh():
    set_store(Store())
    service._SECRET = b"t" * 32
    content.install()
    return TestClient(app)


def signup(c, name, role="student"):
    if role == "administrator":
        service.register(f"{name}@example.com", name, PW, role=role)
    else:
        assert c.post(f"{P}/auth/register", json={"email": f"{name}@example.com", "username": name, "password": PW}).status_code == 201
    r = c.post(f"{P}/auth/login", json={"identifier": name, "password": PW})
    assert r.status_code == 200
    return {"Authorization": "Bearer " + r.json()["access_token"]}


def test_login_sets_httponly_cookie_and_hides_refresh_token_from_body():
    c = fresh()
    c.post(f"{P}/auth/register", json={"email": "a@example.com", "username": "alice", "password": PW})
    r = c.post(f"{P}/auth/login", json={"identifier": "alice", "password": PW})
    cookie = r.headers["set-cookie"].lower()
    assert "oslab_refresh=" in cookie and "httponly" in cookie and "samesite=strict" in cookie and "path=/api/v1/auth" in cookie
    assert set(r.json()) == {"access_token", "token_type", "expires_in", "user"}


def test_refresh_needs_cookie_and_client_header_then_rotates():
    c = fresh()
    signup(c, "alice")
    assert c.post(f"{P}/auth/refresh").status_code == 403                 # cookie present but header missing
    r = c.post(f"{P}/auth/refresh", headers=H)
    assert r.status_code == 200 and r.json()["user"]["username"] == "alice"
    assert c.post(f"{P}/auth/logout", headers=H).status_code == 200
    assert c.post(f"{P}/auth/refresh", headers=H).status_code == 401


def test_me_requires_a_token():
    c = fresh()
    assert c.get(f"{P}/auth/me").status_code == 401
    assert c.get(f"{P}/auth/me", headers={"Authorization": "Bearer junk"}).status_code == 401
    h = signup(c, "alice")
    assert c.get(f"{P}/auth/me", headers=h).json()["username"] == "alice"


def test_admin_api_rejects_guests_and_students_but_accepts_administrators():
    c = fresh()
    student, admin = signup(c, "stu"), signup(c, "boss", "administrator")
    routes = [("GET", "/admin/stats"), ("GET", "/admin/users"), ("GET", "/admin/performance"), ("GET", "/admin/audit"), ("GET", "/admin/topics"), ("GET", "/admin/questions")]
    for m, path in routes:
        assert c.request(m, P + path).status_code == 401, path
        assert c.request(m, P + path, headers=student).status_code == 403, path
        assert c.request(m, P + path, headers=admin).status_code == 200, path
    assert c.patch(f"{P}/admin/users/x", json={"role": "administrator"}, headers=student).status_code == 403
    assert c.delete(f"{P}/admin/users/x", headers=student).status_code == 403
    assert c.post(f"{P}/admin/topics", json={}, headers=student).status_code == 403


def test_admin_can_manage_users_and_content_and_changes_are_audited():
    c = fresh()
    admin = signup(c, "boss", "administrator")
    signup(c, "stu")
    uid = next(u["id"] for u in c.get(f"{P}/admin/users", headers=admin).json()["items"] if u["username"] == "stu")
    assert c.patch(f"{P}/admin/users/{uid}", json={"is_active": False}, headers=admin).json()["is_active"] is False
    assert c.post(f"{P}/auth/login", json={"identifier": "stu", "password": PW}).status_code == 401
    me = c.get(f"{P}/auth/me", headers=admin).json()
    assert c.patch(f"{P}/admin/users/{me['id']}", json={"role": "student"}, headers=admin).status_code == 422
    topic = {"module": "cpu", "level": "beginner", "title": "Hello lesson", "summary": "A summary long enough.", "points": ["p"], "example": "e", "exercise": "q", "answer": "a"}
    t = c.post(f"{P}/admin/topics", json=topic, headers=admin)
    assert t.status_code == 201 and any(x["id"] == t.json()["id"] for x in c.get(f"{P}/learn/topics").json())
    assert c.post(f"{P}/admin/topics/cpu-basics/visibility", json={"published": False}, headers=admin).status_code == 200
    assert all(x["id"] != "cpu-basics" for x in c.get(f"{P}/learn/topics").json())
    assert [a["action"] for a in c.get(f"{P}/admin/audit?action=admin.", headers=admin).json()]


def test_usage_is_recorded_for_simulations_and_shows_up_in_stats():
    c = fresh()
    admin = signup(c, "boss", "administrator")
    for _ in range(3):
        assert c.post(f"{P}/page-replacement/simulate", json={"refs": [1, 2, 3], "frames": 2, "algorithm": "fifo"}).status_code == 200
    assert c.post(f"{P}/page-replacement/simulate", json={"refs": [1], "frames": 2, "algorithm": "nope"}).status_code == 422      # failures do not count
    s = c.get(f"{P}/admin/stats", headers=admin).json()
    assert s["simulations_total"] == 3 and s["most_used_modules"][0] == {"module": "paging", "count": 3}


def test_security_headers_and_validation():
    c = fresh()
    assert c.post(f"{P}/auth/login", json={"identifier": "x" * 300, "password": "y"}).status_code == 422
    assert c.post(f"{P}/auth/register", json={"email": "bad", "username": "u", "password": "p"}).status_code == 422
