"""Offline contract test. When FastAPI/Pydantic are NOT installed, tiny stand-ins let us run the REAL router handlers and
schema classes with the exact JSON the frontend sends. Unknown or missing fields raise (real Pydantic ignores extras, so
a typo like 'max_cylinders' would otherwise pass silently). It also checks every route the frontend calls exists.
Skipped automatically when the real FastAPI is installed (tests/test_api_*.py cover that case)."""
import importlib
import inspect
import json
import pathlib
import re
import sys
import types
import typing

try:
    import fastapi  # noqa: F401
    HAVE_REAL = True
except ImportError:
    HAVE_REAL = False

MISSING = object()


def _install_stubs():
    fa = types.ModuleType("fastapi")

    class HTTPException(Exception):
        def __init__(self, status_code, detail=None, headers=None):
            self.status_code, self.detail, self.headers = status_code, detail, headers

    class Depends:
        def __init__(self, dependency=None):
            self.dependency = dependency

    class APIRouter:
        def __init__(self, prefix="", tags=None, dependencies=None):
            self.prefix, self.routes, self.dependencies = prefix, [], list(dependencies or [])

        def _reg(self, method, path):
            def deco(fn):
                self.routes.append((method, self.prefix + path, fn))
                return fn
            return deco

        def get(self, path, **_):
            return self._reg("GET", path)

        def post(self, path, **_):
            return self._reg("POST", path)

        def put(self, path, **_):
            return self._reg("PUT", path)

        def patch(self, path, **_):
            return self._reg("PATCH", path)

        def delete(self, path, **_):
            return self._reg("DELETE", path)

    fa.APIRouter, fa.HTTPException, fa.Depends = APIRouter, HTTPException, Depends
    fa.Header = lambda default=None, **_: default
    fa.Request = fa.Response = object
    pd = types.ModuleType("pydantic")

    class FieldInfo:
        def __init__(self, default=MISSING, default_factory=None):
            self.default, self.default_factory = default, default_factory

    def Field(default=MISSING, *, default_factory=None, **_):
        return FieldInfo(default, default_factory)

    def coerce(ann, v):
        origin, args = typing.get_origin(ann), typing.get_args(ann)
        if origin is list and args and inspect.isclass(args[0]) and issubclass(args[0], BaseModel):
            return [args[0](**x) for x in v]
        return v

    class BaseModel:
        def __init__(self, **kw):
            hints = typing.get_type_hints(type(self))
            extra = set(kw) - set(hints)
            if extra:
                raise ValueError(f"{type(self).__name__}: frontend sends unknown field(s) {sorted(extra)}")
            for name, ann in hints.items():
                if name in kw:
                    v = kw[name]
                else:
                    d = getattr(type(self), name, MISSING)
                    if isinstance(d, FieldInfo):
                        d = d.default if d.default is not MISSING else (d.default_factory() if d.default_factory else MISSING)
                    if d is MISSING:
                        raise ValueError(f"{type(self).__name__}: required field '{name}' missing")
                    v = d
                setattr(self, name, coerce(ann, v))

        def model_dump(self, exclude_none=False):
            out = {}
            for name in typing.get_type_hints(type(self)):
                v = getattr(self, name)
                if isinstance(v, list):
                    v = [x.model_dump(exclude_none) if isinstance(x, BaseModel) else x for x in v]
                if exclude_none and v is None:
                    continue
                out[name] = v
            return out

    pd.BaseModel, pd.Field, pd.StrictInt = BaseModel, Field, int
    return fa, pd


def _routers():
    mods = {}
    for name in ["cpu", "paging", "disk", "memory", "deadlock", "phase5", "accounts", "admin", "deps"]:
        m = importlib.import_module(f"app.api.v1.{name}")
        mods[name] = m
    out = []
    for m in mods.values():
        out += [v for v in vars(m).values() if v.__class__.__name__ == "APIRouter" and v not in out]
    return mods, out


PROCS = [{"pid": "P1", "arrival": 0, "burst": 5, "priority": 2, "queue": 0}, {"pid": "P2", "arrival": 1, "burst": 4, "priority": 1, "queue": 0}]
DL = {"available": [3, 3, 2], "allocation": [[0, 1, 0], [2, 0, 0], [3, 0, 2], [2, 1, 1], [0, 0, 2]], "maximum": [[7, 5, 3], [3, 2, 2], [9, 0, 2], [2, 2, 2], [4, 3, 3]]}
DD = {"available": [0, 0], "allocation": [[1, 0], [0, 1]], "request": [[0, 1], [1, 0]]}
MEMOPS = [{"op": "alloc", "pid": "P1", "size": 212}, {"op": "free", "pid": "P1"}, {"op": "compact"}]
FSOPS = [{"op": "mkdir", "path": "/d"}, {"op": "create", "path": "/d/a", "size": 3}, {"op": "read", "path": "/d/a"}]
VM = {"page_size": 1024, "virtual_size": 8192, "physical_size": 4096, "tlb_size": 2, "tlb_policy": "lru", "addresses": [0, 1024, 2500]}
REFS = [7, 0, 1, 2, 0, 3]
WL = {"cpu": {"quantum": 2, "processes": [{"pid": "P1", "arrival": 0, "burst": 5, "priority": 0}, {"pid": "P2", "arrival": 1, "burst": 3, "priority": 0}]},
      "paging": {"refs": REFS, "frames": 3}, "disk": {"requests": [98, 183, 37], "head": 53, "max_cylinder": 199, "direction": "up"},
      "memory": {"blocks": [100, 500], "ops": MEMOPS[:1], "mode": "variable"}, "fs": {"total_blocks": 16, "block_size_kb": 1, "ops": FSOPS},
      "vm": {"page_size": 1024, "virtual_size": 8192, "physical_size": 2048, "tlb_size": 2, "tlb_policy": "lru", "addresses": [0, 1024, 0]}}
SID = "contract-test-session"


def _calls(mods):
    S = importlib.import_module("app.schemas.modules")
    C = importlib.import_module("app.schemas.cpu")
    p, a, c = mods["phase5"], mods["paging"], mods["cpu"]
    # (handler, schema class or None, payload mirrored from what the frontend page builds)
    return [
        (c.run_simulation, C.SimulateRequest, {"algorithm": "rr", "processes": PROCS, "quantum": 2, "levels": None}),
        (c.run_comparison, C.CompareRequest, {"processes": PROCS, "configs": [{"algorithm": "fcfs", "quantum": None, "levels": None}, {"algorithm": "rr", "quantum": 2, "levels": None}]}),
        (a.simulate, S.PagingSimulate, {"refs": REFS, "frames": 3, "algorithm": "fifo"}),
        (a.compare, S.PagingCompare, {"refs": REFS, "frames": 3, "algorithms": ["fifo", "lru"]}),
        (a.belady, S.PagingBelady, {"refs": REFS, "algorithm": "fifo", "max_frames": 7}),
        (mods["disk"].simulate, S.DiskSimulate, {"requests": [98, 183, 37], "head": 53, "max_cylinder": 199, "direction": "up", "count_jump": True, "algorithm": "scan"}),
        (mods["disk"].compare, S.DiskCompare, {"requests": [98, 183, 37], "head": 53, "max_cylinder": 199, "direction": "up", "count_jump": True, "algorithms": ["fcfs", "sstf"]}),
        (mods["memory"].simulate, S.MemorySimulate, {"blocks": [100, 500, 200], "ops": MEMOPS, "mode": "variable", "strategy": "first_fit"}),
        (mods["memory"].compare, S.MemoryCompare, {"blocks": [100, 500, 200], "ops": MEMOPS, "mode": "variable", "strategies": ["first_fit", "best_fit"]}),
        (mods["deadlock"].safety, S.DeadlockState, DL),
        (mods["deadlock"].request, S.DeadlockRequest, {**DL, "pid": 1, "request": [1, 0, 2]}),
        (mods["deadlock"].detect, S.DeadlockDetect, DD), (mods["deadlock"].recover, S.DeadlockDetect, DD), (mods["deadlock"].graph, S.DeadlockDetect, DD),
        (p.p_simulate, S.ProcSimulate, {"quantum": 2, "processes": [{"pid": "init", "arrival": 0, "bursts": [3, 2, 2], "priority": 1, "parent": None, "memory": 64},
                                                                    {"pid": "sh", "arrival": 1, "bursts": [4], "priority": 1, "parent": "init", "memory": 128}]}),
        (p.p_ipc, S.IpcRequest, {"mechanism": "pipe", "capacity": 2, "ops": [{"by": "W", "op": "send", "data": "hello"}, {"by": "R", "op": "recv"}]}),
        (p.p_ipc, S.IpcRequest, {"mechanism": "shared_memory", "capacity": 2, "ops": [{"by": "A", "op": "write", "key": "x", "data": "1"}, {"by": "B", "op": "read", "key": "x"}]}),
        (p.p_threads, S.ThreadsRequest, {"threads": 3, "work": 4}),
        (p.s_run, S.SyncRun, {"scenario": "producer_consumer", "params": {"buffer": 3, "producers": 1, "consumers": 1, "items": 5, "synchronized": True, "quantum": 1}}),
        (p.s_run, S.SyncRun, {"scenario": "dining_philosophers", "params": {"philosophers": 5, "meals": 2, "strategy": "naive", "quantum": 1}}),
        (p.f_simulate, S.FsSimulate, {"total_blocks": 16, "block_size_kb": 1, "ops": FSOPS, "method": "indexed"}),
        (p.f_compare, S.FsCompare, {"total_blocks": 16, "block_size_kb": 1, "ops": FSOPS, "methods": ["contiguous", "linked"]}),
        (p.v_translate, S.VmTranslate, {**VM, "replacement": "lru"}), (p.v_compare, S.VmCompare, {**VM, "policies": ["fifo", "lru"]}),
        (p.v_ws, S.WorkingSetRequest, {"refs": REFS, "delta": 4}),
        (p.v_thrash, S.ThrashingRequest, {"total_frames": 16, "working_set_size": 4, "refs_per_process": 400, "max_processes": 12, "fault_cost": 50}),
        *[(p.a_compare, S.AnalyzerRequest, {"module": m, "workload": w, "algorithms": al}) for (m, w, al) in
          [("cpu", WL["cpu"], ["fcfs", "rr"]), ("paging", WL["paging"], ["fifo", "lru"]), ("disk", WL["disk"], ["fcfs", "sstf"]),
           ("memory", WL["memory"], ["first_fit", "best_fit"]), ("fs", WL["fs"], ["contiguous", "linked"]), ("vm", WL["vm"], ["fifo", "lru"])]],
        (p.a_report, S.AnalyzerRequest, {"module": "paging", "workload": WL["paging"], "algorithms": ["fifo", "lru"]}),
        (p.t_exec, S.TerminalRequest, {"session_id": SID, "command": "os-info"}),
    ]


def test_frontend_payloads_match_schemas_and_run_through_real_handlers():
    if HAVE_REAL:
        return
    fa, pd = _install_stubs()
    saved = {k: sys.modules.get(k) for k in ("fastapi", "pydantic")}
    mods_to_drop = [k for k in sys.modules if k.startswith("app.api") or k.startswith("app.schemas")]
    for k in mods_to_drop:
        del sys.modules[k]
    sys.modules["fastapi"], sys.modules["pydantic"] = fa, pd
    from app.auth import content as _content, service as _service
    from app.auth.store import Store as _Store, set_store as _set_store
    from app.engines.learn import quiz as _quiz
    _set_store(_Store()); _content.install()
    try:
        mods, _ = _routers()
        n = 0
        for handler, schema, payload in _calls(mods):
            out = handler(schema(**payload))
            assert out, handler.__name__
            n += 1
        assert n >= 29
        # big CPU run: the API payload is bounded and reports the real step count
        from app.engines.cpu import Process, simulate as cpu_sim
        common = importlib.import_module("app.api.v1.common")
        big = cpu_sim([Process(f"P{i}", i % 50, 60) for i in range(60)], "rr", 1)
        body = common.trace_payload(big)
        assert len(body["steps"]) <= 5000 and body["truncated"] is True and body["total_steps"] == big.total_steps > 5000
        small = common.trace_payload(cpu_sim([Process("A", 0, 3)], "fcfs"))
        assert small["truncated"] is False and small["total_steps"] == len(small["steps"])
        # a typo'd field name must be caught by the stub (real Pydantic would silently ignore it)
        S = importlib.import_module("app.schemas.modules")
        try:
            S.DiskSimulate(requests=[1], head=0, max_cylinders=9, algorithm="fcfs")
            raise AssertionError("typo not detected")
        except ValueError:
            pass
        # GET handlers
        p = mods["phase5"]
        assert len(p.s_catalog()) == 7 and len(p.a_catalog()) == 6 and len(p.l_modules()) == 10
        assert len(p.l_topics("cpu")) == 3 and p.l_topic("cpu-basics")["level"] == "beginner"
        q = p.q_build("paging", "beginner")["questions"]
        g = p.q_grade(S.QuizGrade(question_ids=[x["id"] for x in q], answers={}))
        assert g["total"] == len(q) and g["score"] == 0
        # engine validation errors become HTTP 422 through the real error wrapper
        try:
            p.s_run(S.SyncRun(scenario="nope", params={}))
            raise AssertionError("expected HTTP error")
        except sys.modules["fastapi"].HTTPException as e:
            assert e.status_code == 422
        # terminal: injection is refused by the real route
        r = p.t_exec(S.TerminalRequest(session_id=SID, command="ls; rm -rf /"))
        assert r["ok"] is False
    finally:
        _set_store(None); _quiz.PROVIDER = None
        for k in [k for k in sys.modules if k.startswith("app.api") or k.startswith("app.schemas")]:
            del sys.modules[k]
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v


def _frontend_calls():
    root = pathlib.Path(__file__).resolve().parents[2] / "frontend" / "src"
    if not root.exists():
        return None
    calls = set()
    for f in root.rglob("*.ts*"):
        src = f.read_text()
        for m in re.finditer(r"\b(post|get|put|patch|del|useCatalog)(?:<[^()]*?>)?\(\s*([`\"])(/[^`\"]*)\2", src):
            fn, path = m.group(1), re.sub(r"\$\{[^}]*\}", "{x}", m.group(3)).split("?")[0]
            calls.add(({"post": "POST", "put": "PUT", "patch": "PATCH", "del": "DELETE"}.get(fn, "GET"), path, f.name))
        if f.name == "api.ts":
            for m in re.finditer(r"request<[^()]*?>\(\"(/[^\"]+)\"(,\s*\{ method: \"POST\")?", src):
                calls.add(("POST" if m.group(2) else "GET", m.group(1), f.name))
    return calls


def test_every_route_the_frontend_calls_exists_with_the_right_method():
    if HAVE_REAL:
        return
    calls = _frontend_calls()
    if calls is None:
        return
    fa, pd = _install_stubs()
    saved = {k: sys.modules.get(k) for k in ("fastapi", "pydantic")}
    for k in [k for k in sys.modules if k.startswith("app.api") or k.startswith("app.schemas")]:
        del sys.modules[k]
    sys.modules["fastapi"], sys.modules["pydantic"] = fa, pd
    try:
        _, routers = _routers()
        routes = [(m, re.compile("^" + re.sub(r"\{[^}]+\}", "[^/]+", p) + "$")) for r in routers for (m, p, _) in r.routes]
        assert len(calls) >= 30, f"only found {len(calls)} frontend calls: parser broken?"
        missing = [(m, p, f) for (m, p, f) in sorted(calls) if not any(m == rm and rx.match(p) for rm, rx in routes)]
        assert not missing, f"frontend calls routes that do not exist: {missing}"
    finally:
        for k in [k for k in sys.modules if k.startswith("app.api") or k.startswith("app.schemas")]:
            del sys.modules[k]
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v



# ======================= accounts, admin and authorization =======================
class FakeResp:
    def __init__(self):
        self.set, self.deleted = {}, []

    def set_cookie(self, key, value, **kw):
        self.set[key] = (value, kw)

    def delete_cookie(self, key, **kw):
        self.deleted.append(key)


class FakeReq:
    def __init__(self, headers=None, cookies=None, ip="203.0.113.7"):
        self.headers = {k.lower(): v for k, v in (headers or {}).items()}
        self.cookies = cookies or {}
        self.client = types.SimpleNamespace(host=ip)


import contextlib


@contextlib.contextmanager
def _stubbed():
    fa, pd = _install_stubs()
    saved = {k: sys.modules.get(k) for k in ("fastapi", "pydantic")}
    for k in [k for k in sys.modules if k.startswith("app.api") or k.startswith("app.schemas")]:
        del sys.modules[k]
    sys.modules["fastapi"], sys.modules["pydantic"] = fa, pd
    from app.auth import content, service
    from app.auth.store import Store, set_store
    from app.engines.learn import quiz
    old = (service._SECRET, service.clock)
    set_store(Store()); service._SECRET = b"c" * 32; content.install()
    try:
        yield _routers()[0], fa
    finally:
        set_store(None); quiz.PROVIDER = None; service._SECRET, service.clock = old
        for k in [k for k in sys.modules if k.startswith("app.api") or k.startswith("app.schemas")]:
            del sys.modules[k]
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v


def _raises(fa, status, fn, *a, **kw):
    try:
        fn(*a, **kw)
    except fa.HTTPException as e:
        assert e.status_code == status, (status, e.status_code, e.detail)
        return e
    raise AssertionError(f"expected HTTP {status}")


def test_account_endpoints_cookies_and_csrf_header():
    if HAVE_REAL:
        return
    with _stubbed() as (mods, fa):
        acc, S = mods["accounts"], importlib.import_module("app.schemas.auth")
        user = acc.register(S.RegisterIn(email="ann@example.com", username="ann", password="Passw0rd-ok"), FakeReq())
        assert user["role"] == "student" and "password_hash" not in user
        r = FakeResp()
        out = acc.login(S.LoginIn(identifier="ann", password="Passw0rd-ok"), FakeReq(), r)
        assert out["token_type"] == "bearer" and out["user"]["username"] == "ann" and "refresh" not in json.dumps(out)      # refresh token is NOT in the body
        value, kw = r.set["oslab_refresh"]
        assert kw["httponly"] is True and kw["samesite"] == "strict" and kw["path"] == "/api/v1/auth" and len(value) > 40
        _raises(fa, 403, acc.refresh, FakeReq(cookies={"oslab_refresh": value}), FakeResp())                     # no X-OSLab-Client header
        r2 = FakeResp()
        out2 = acc.refresh(FakeReq({"X-OSLab-Client": "web"}, {"oslab_refresh": value}), r2)
        assert out2["access_token"] and r2.set["oslab_refresh"][0] != value                                       # rotated
        from app.auth import service as _svc
        _t = _svc.clock()
        _svc.clock = lambda: _t + 60                                                                               # replay long after the rotation
        r3 = FakeResp()
        _raises(fa, 401, acc.refresh, FakeReq({"X-OSLab-Client": "web"}, {"oslab_refresh": value}), r3)          # replay of the old one
        assert r3.deleted == ["oslab_refresh"]
        _raises(fa, 401, acc.login, S.LoginIn(identifier="ann", password="nope-Pass1"), FakeReq(), FakeResp())
        _raises(fa, 403, acc.logout, FakeReq(cookies={"oslab_refresh": r2.set["oslab_refresh"][0]}), FakeResp())
        r4 = FakeResp()
        assert acc.logout(FakeReq({"X-OSLab-Client": "web"}, {"oslab_refresh": r2.set["oslab_refresh"][0]}), r4) == {"ok": True} and r4.deleted == ["oslab_refresh"]
        _raises(fa, 422, acc.register, S.RegisterIn(email="bad", username="x", password="y"), FakeReq())


def test_login_is_rate_limited_per_address():
    if HAVE_REAL:
        return
    with _stubbed() as (mods, fa):
        acc, S = mods["accounts"], importlib.import_module("app.schemas.auth")
        acc._login_limiter.__init__(10, 60)
        codes = []
        for _ in range(12):
            try:
                acc.login(S.LoginIn(identifier="nobody", password="x"), FakeReq(ip="198.51.100.9"), FakeResp())
            except fa.HTTPException as e:
                codes.append(e.status_code)
        assert codes == [401] * 10 + [429, 429]


def test_dependencies_enforce_authentication_and_roles():
    if HAVE_REAL:
        return
    from app.auth import admin as ops, service, tokens
    with _stubbed() as (mods, fa):
        deps = mods["deps"]
        stu = service.register("stu@example.com", "stu", "Passw0rd-ok")
        adm = service.register("adm@example.com", "adm", "Passw0rd-ok", role="administrator")
        tok = lambda u: "Bearer " + service.login(u["username"], "Passw0rd-ok")[1]
        for bad in (None, "", "Basic abc", "Bearer", "Bearer not.a.token", "bearer  ", "Bearer " + tokens.encode({"sub": stu["id"], "exp": 9e12, "typ": "access"}, b"w" * 32)):
            _raises(fa, 401, deps.require_user, bad)
            assert deps.optional_user(bad) is None
        assert deps.require_user(tok(stu))["username"] == "stu" and deps.optional_user(tok(adm))["role"] == "administrator"
        _raises(fa, 403, deps.require_admin, deps.require_user(tok(stu)))
        assert deps.require_admin(deps.require_user(tok(adm)))["username"] == "adm"
        ops.update_user(adm, stu["id"], is_active=False)
        disabled_users_token = "Bearer " + tokens.create_access_token(stu["id"], service.secret())     # correctly signed, not expired...
        _raises(fa, 401, deps.require_user, disabled_users_token)                                         # ...but the account is disabled


def test_every_admin_route_requires_an_administrator():
    if HAVE_REAL:
        return
    with _stubbed() as (mods, fa):
        adm, deps, acc = mods["admin"], mods["deps"], mods["accounts"]
        routers = [v for v in vars(adm).values() if v.__class__.__name__ == "APIRouter"]
        admin_router = next(r for r in routers if r.prefix == "/admin")
        assert any(d.dependency is deps.require_admin for d in admin_router.dependencies), "router-level admin guard missing"
        assert len(admin_router.routes) >= 18
        # no '/admin' route may live on any other router (it would bypass the guard)
        for name, m in mods.items():
            for r in [v for v in vars(m).values() if v.__class__.__name__ == "APIRouter" and v is not admin_router]:
                assert not any("/admin" in p for _, p, _ in r.routes), (name, r.prefix)
        # user-data routes depend on a signed-in user
        for _, path, fn in acc.me_router.routes + [rt for rt in acc.router.routes if rt[1].endswith("/me")]:
            deps_used = [p.default.dependency for p in inspect.signature(fn).parameters.values() if hasattr(p.default, "dependency")]
            assert deps.require_user in deps_used, path
        # every state-changing admin handler also receives the acting admin (for the audit log)
        for method, path, fn in admin_router.routes:
            if method != "GET":
                assert any(getattr(p.default, "dependency", None) is deps.require_admin for p in inspect.signature(fn).parameters.values()), path


def test_admin_handlers_with_the_payloads_the_admin_page_sends():
    if HAVE_REAL:
        return
    from app.auth import service
    with _stubbed() as (mods, fa):
        a, A = mods["admin"], importlib.import_module("app.schemas.auth")
        boss = service.register("boss@example.com", "boss", "Passw0rd-ok", role="administrator")
        stu = service.register("stu@example.com", "stu", "Passw0rd-ok")
        req = FakeReq()
        st = a.stats()
        assert st["students"] == 1 and st["administrators"] == 1 and "simulations_total" in st
        assert a.users(search="st", role=None, active=None, limit=25, offset=0)["total"] == 1
        assert a.patch_user(stu["id"], A.UserPatch(role="administrator"), req, boss)["role"] == "administrator"
        assert a.patch_user(stu["id"], A.UserPatch(is_active=True, role="student"), req, boss)["role"] == "student"
        _raises(fa, 422, a.patch_user, boss["id"], A.UserPatch(role="student"), req, boss)                       # cannot demote yourself
        assert a.reset_password(stu["id"], A.PasswordReset(new_password="Another9pass"), req, boss) == {"ok": True}
        topic = a.create_topic(A.TopicIn(module="cpu", level="beginner", title="Hello lesson", summary="A summary long enough.", points=["p1"], example="e", exercise="q", answer="a"), req, boss)
        assert topic["id"].startswith("c-")
        assert a.update_topic(topic["id"], A.TopicIn(module="cpu", level="advanced", title="Hello lesson 2", summary="A summary long enough.", points=["p1"], example="e", exercise="q", answer="a", published=False), req, boss)["level"] == "advanced"
        assert a.topic_visibility("cpu-basics", A.Visibility(published=False), req, boss) == {"ok": True}
        assert len(a.topics()) == 31 and next(t for t in a.topics() if t["id"] == "cpu-basics")["published"] is False
        q = a.create_question(A.QuestionIn(module="disk", level="beginner", prompt="Is SSTF fair?", options=["Yes", "No"], correct_index=1, explanation="It can starve."), req, boss)
        assert a.question_visibility("m|cpu|0", A.Visibility(published=False), req, boss) == {"ok": True} and len(a.questions()) == 31
        assert a.delete_question(q["id"], req, boss) == {"ok": True} and a.delete_topic(topic["id"], req, boss) == {"ok": True}
        _raises(fa, 422, a.delete_topic, "cpu-basics", req, boss)                                                  # built-ins cannot be deleted
        _raises(fa, 422, a.create_question, A.QuestionIn(module="disk", level="beginner", prompt="Bad one?", options=["a", "b"], correct_index=5, explanation="x"), req, boss)
        assert a.performance()["students"] and a.audit(100, "admin.")
        assert a.delete_user(stu["id"], req, boss) == {"ok": True}
        _raises(fa, 422, a.delete_user, "no-such-user", req, boss)


def test_progress_and_quiz_attempts_are_stored_per_user():
    if HAVE_REAL:
        return
    from app.auth import admin as ops, service
    with _stubbed() as (mods, fa):
        acc, p, S, A = mods["accounts"], mods["phase5"], importlib.import_module("app.schemas.modules"), importlib.import_module("app.schemas.auth")
        u = service.register("kim@example.com", "kim", "Passw0rd-ok")
        assert acc.put_progress(A.ProgressIn(topic_id="cpu-basics", completed=True), u) == {"completed": ["cpu-basics"]}
        assert acc.get_progress(u) == {"completed": ["cpu-basics"]}
        _raises(fa, 422, acc.put_progress, A.ProgressIn(topic_id="../x", completed=True), u)
        qs = p.q_build("paging", "beginner")["questions"]
        p.q_grade(S.QuizGrade(question_ids=[q["id"] for q in qs], answers={}, level="beginner"), u)
        p.q_grade(S.QuizGrade(question_ids=[q["id"] for q in qs], answers={}), None)                              # guest attempt is counted too
        h = acc.quiz_history(u)
        assert len(h) == 1 and h[0]["module"] == "paging" and h[0]["level"] == "beginner" and h[0]["total"] == len(qs)
        assert ops.stats()["quiz_attempts"] == 2


def test_usage_rules_cover_every_simulation_endpoint_the_frontend_calls():
    from app.core.usage import usage_for, MODULE_OF
    assert usage_for("POST", "/api/v1/cpu/simulate", 200) == ("cpu", "simulate")
    assert usage_for("POST", "/api/v1/page-replacement/belady", 200) == ("paging", "belady")
    assert usage_for("POST", "/api/v1/terminal/exec", 200) == ("terminal", "exec")
    assert usage_for("POST", "/api/v1/analyzer/report", 200) == ("perf", "report")
    for no in [("GET", "/api/v1/cpu/simulate", 200), ("POST", "/api/v1/cpu/simulate", 422), ("POST", "/api/v1/auth/login", 200), ("POST", "/api/v1/admin/topics", 200),
               ("POST", "/api/v1/quiz/grade", 200), ("POST", "/api/v1/cpu/simulate/extra", 200), ("POST", "/api/v1/unknown/run", 200)]:
        assert usage_for(*no) is None, no
    calls = _frontend_calls()
    if calls:
        for method, path, _ in calls:
            first = path.strip("/").split("/")
            if method == "POST" and first[0] in MODULE_OF and len(first) == 2 and first[1] not in ("algorithms", "strategies", "catalog"):
                assert usage_for("POST", "/api/v1" + path, 200), path
