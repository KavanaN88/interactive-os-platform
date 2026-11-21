"""Every TypeScript interface a page uses for API data must only read keys the backend really returns.
Parses the interfaces from the frontend source and compares them with REAL backend output (skipped if the frontend is absent)."""
import pathlib
import re

from app.auth import admin, content, service
from app.auth.store import Store, set_store
from app.engines.analyzer import engine as analyzer
from app.engines.learn import quiz
from app.engines.learn.content import MODULES, TOPICS
from app.engines.vm import engine as vm

SRC = pathlib.Path(__file__).resolve().parents[2] / "frontend" / "src" / "pages"


def _body(text, name):
    m = re.search(r"interface\s+" + name + r"(?:\s+extends\s+(\w+))?\s*\{", text)
    if not m:
        raise AssertionError(f"interface {name} not found")
    i, depth = m.end(), 1
    j = i
    while depth:
        depth += {"{": 1, "}": -1}.get(text[j], 0)
        j += 1
    return m.group(1), text[i:j - 1]


def keys(text, name):
    """Top-level keys of an interface (including those inherited through `extends`)."""
    parent, body = _body(text, name)
    flat = body
    while re.search(r"\{[^{}]*\}", flat):
        flat = re.sub(r"\{[^{}]*\}", "", flat)
    own = {k for k, opt in re.findall(r"(\w+)(\??)\s*:", flat) if not opt}        # optional keys (`name?:`) may legitimately be absent
    return own | (keys(text, parent) if parent else set())


def nested(text, name, field):
    """Keys of the object type inside `field: { ... }[]` (or `{...}` / Record values) of an interface."""
    _, body = _body(text, name)
    m = re.search(r"\b" + field + r"\??\s*:\s*\{", body)
    assert m, f"{name}.{field} has no inline object type"
    i, depth, j = m.end(), 1, m.end()
    while depth:
        depth += {"{": 1, "}": -1}.get(body[j], 0)
        j += 1
    inner = body[i:j - 1]
    while re.search(r"\{[^{}]*\}", inner):
        inner = re.sub(r"\{[^{}]*\}", "", inner)
    return {k for k, opt in re.findall(r"(\w+)(\??)\s*:", inner) if not opt}


def check(name, wanted, sample, where=""):
    missing = set(wanted) - set(sample)
    assert not missing, f"{where}{name}: the page reads {sorted(missing)} but the backend does not return them (it returns {sorted(sample)})"


def test_admin_page_shapes_match_backend():
    if not SRC.exists():
        return
    t = (SRC / "Admin.tsx").read_text()
    set_store(Store())
    old = service._SECRET
    service._SECRET = b"s" * 32
    content.install()
    try:
        a = service.register("boss@example.com", "boss", "Passw0rd-ok", role="administrator")
        s = service.register("stu@example.com", "stu", "Passw0rd-ok")
        service.record_usage("cpu", "simulate", s["id"])
        service.record_quiz_attempt(s["id"], "cpu", "beginner", {"score": 1, "total": 2, "percent": 50.0, "by_level": {}})
        service.set_progress(s["id"], "cpu-basics", True)
        stats, perf, users = admin.stats(), admin.performance(), admin.list_users()
        check("Stats", keys(t, "Stats"), stats)
        check("Stats.most_used_modules", nested(t, "Stats", "most_used_modules"), stats["most_used_modules"][0])
        check("Stats.simulations_per_day", nested(t, "Stats", "simulations_per_day"), stats["simulations_per_day"][0])
        check("UsersRes", keys(t, "UsersRes"), users)
        check("UserRow", keys(t, "UserRow"), users["items"][0])
        check("Perf", keys(t, "Perf"), perf)
        check("Perf.students", nested(t, "Perf", "students"), perf["students"][0])
        check("Perf.modules", nested(t, "Perf", "modules"), perf["modules"][0])
        check("AuditRow", keys(t, "AuditRow"), admin.audit_list()[0])
        topics = admin.list_topics()
        check("TopicRow", keys(t, "TopicRow"), topics[0])
        admin.create_topic(a, {"module": "cpu", "level": "beginner", "title": "Custom one", "summary": "A long enough summary.", "points": ["p"], "example": "e", "exercise": "q", "answer": "a"})
        check("TopicRow(custom)", keys(t, "TopicRow"), admin.list_topics()[-1])
        check("TopicFull", keys(t, "TopicFull"), admin.get_topic_admin("c-1"))
        check("TopicFull(built-in)", keys(t, "TopicFull"), admin.get_topic_admin("cpu-basics") | {"published": True})
        admin.create_question(a, {"module": "cpu", "level": "beginner", "prompt": "Pick the right one", "options": ["a", "b"], "correct_index": 0, "explanation": "because"})
        qs = admin.list_questions()
        check("QuestionRow(built-in)", keys(t, "QuestionRow"), qs[0])
        check("QuestionRow(custom)", keys(t, "QuestionRow"), qs[-1])
        auth = (SRC.parent / "components" / "AuthProvider.tsx").read_text()
        check("User", keys(auth, "User"), service.public(service.get_user(s["id"])))
    finally:
        set_store(None)
        service._SECRET = old
        quiz.PROVIDER = None


def test_learn_page_shapes_match_backend():
    if not SRC.exists():
        return
    t = (SRC / "Learn.tsx").read_text()
    check("Mod", keys(t, "Mod"), {"id": 1, "name": 1, "topics": 1})          # built by the /learn/modules handler (id, name, topics)
    brief = {k: TOPICS[0][k] for k in ("id", "module", "level", "title", "summary")}
    check("TopicBrief", keys(t, "TopicBrief"), brief)
    check("Topic", keys(t, "Topic"), TOPICS[0])
    q = quiz.build("cpu", "all", seed=1)
    check("Question(mcq)", keys(t, "Question"), next(x for x in q if x["type"] == "mcq"))
    check("Question(numeric)", keys(t, "Question"), next(x for x in q if x["type"] == "numeric"))
    g = quiz.grade([x["id"] for x in q], {})
    check("Graded", keys(t, "Graded"), g)
    check("Graded.results", nested(t, "Graded", "results"), g["results"][0])
    check("Graded.by_level", {"correct", "total"}, next(iter(g["by_level"].values())))


def test_analyzer_and_vm_page_shapes_match_backend():
    if not SRC.exists():
        return
    a = (SRC / "Analyzer.tsx").read_text()
    cat = analyzer.catalog()[0]
    check("Cat", keys(a, "Cat"), cat)
    check("Cat.algorithms", nested(a, "Cat", "algorithms"), cat["algorithms"][0])
    wl = {"processes": [{"pid": "P1", "arrival": 0, "burst": 3}, {"pid": "P2", "arrival": 1, "burst": 2}], "quantum": 2}
    r = analyzer.compare("cpu", wl, ["fcfs", "rr"])
    check("Result", keys(a, "Result"), r)
    check("Result.runs", nested(a, "Result", "runs"), r["runs"][0])
    for module, w in [("cpu", wl), ("paging", {"refs": [1, 2, 3], "frames": 2}), ("disk", {"requests": [1, 5], "head": 2, "max_cylinder": 9}), ("vm", {"page_size": 8, "virtual_size": 64, "physical_size": 32, "addresses": [0, 9]})]:
        c = next(x for x in analyzer.catalog() if x["module"] == module)
        res = analyzer.compare(module, w, c["defaults"][:2])
        for key, _label, _lower in c["metrics"]:
            assert key in res["runs"][0]["metrics"], (module, key)            # every column the table shows exists in the metrics
    v = (SRC / "VirtualMemory.tsx").read_text()
    ws = vm.working_set([1, 2, 1, 3], 2)
    check("Ws", keys(v, "Ws"), ws)
    check("Ws.rows", nested(v, "Ws", "rows"), ws["rows"][0])
    th = vm.thrashing(16, 4)
    check("Th", keys(v, "Th"), th)
    check("Th.rows", nested(v, "Th", "rows"), th["rows"][0])
