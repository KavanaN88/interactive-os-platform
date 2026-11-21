try:
    import pytest
except ImportError:
    from tests._shim import pytest
from app.engines.errors import ValidationError
from app.engines.learn.content import MODULES, TOPICS
from app.engines.learn import quiz
from app.engines.cpu import Process as P, simulate as cpu
from app.engines.paging.engine import simulate as paging, belady
from app.engines.disk.engine import simulate as disk
from app.engines.memory.engine import simulate as mem
from app.engines.deadlock.engine import safety
from app.engines.fs.engine import simulate as fs
from app.engines.vm.engine import thrashing, translate
from app.engines.process.engine import simulate as proc

def test_every_module_has_three_levels_with_complete_fields():
    for mid, _ in MODULES:
        ts = [t for t in TOPICS if t["module"] == mid]
        assert [t["level"] for t in ts] == ["beginner", "intermediate", "advanced"], mid
    for t in TOPICS:
        assert all(t[k] for k in ("id", "title", "summary", "example", "exercise", "answer")) and len(t["points"]) >= 3
    assert len({t["id"] for t in TOPICS}) == len(TOPICS) == 30

# ---- the numbers quoted in the lessons are recomputed from the engines ----
def test_lesson_numbers_match_the_simulators():
    m = cpu([P("P1", 0, 5), P("P2", 1, 3), P("P3", 2, 2)], "fcfs").result["metrics"]
    assert m["avg_waiting_time"] == 3.3333 and m["avg_turnaround_time"] == 6.6667
    rr = cpu([P("P1", 0, 5), P("P2", 1, 3)], "rr", 2)
    assert [(g["pid"], g["start"], g["end"]) for g in rr.result["gantt"]] == [("P1", 0, 2), ("P2", 2, 4), ("P1", 4, 6), ("P2", 6, 7), ("P1", 7, 8)]
    assert rr.result["metrics"]["context_switches"] == 4 and cpu([P("P1", 0, 5), P("P2", 1, 3)], "fcfs").result["metrics"]["context_switches"] == 1
    assert cpu([P("P1", 0, 6), P("P2", 1, 1)], "mlfq", levels=[2, 4]).result["processes"][1]["response"] == 1
    assert proc([{"pid": "A", "arrival": 0, "bursts": [4]}, {"pid": "B", "arrival": 0, "bursts": [4]}], 2).result["metrics"]["context_switches"] == 3
    f = paging([1, 2, 3, 1, 4], 3, "fifo")
    assert f.result["metrics"]["faults"] == 4 and f.result["metrics"]["hit_ratio"] == 20.0 and f.steps[-1].state["victim"] == 1
    c = [7, 0, 1, 2, 0, 3, 0, 4, 2, 3, 0, 3, 2, 1, 2, 0, 1, 7, 0, 1]
    assert [paging(c, 3, a).result["metrics"]["faults"] for a in ("fifo", "lru", "optimal")] == [15, 12, 9]
    b = belady([1, 2, 3, 4, 1, 2, 5, 1, 2, 3, 4, 5], "fifo", 4)
    assert [x["faults"] for x in b["curve"]][2:4] == [9, 10] and not belady([1, 2, 3, 4, 1, 2, 5, 1, 2, 3, 4, 5], "lru", 4)["anomaly"]
    q = [98, 183, 37, 122, 14, 124, 65, 67]
    tot = lambda a, d="up": disk(q, 53, 199, d, a).result["metrics"]["total_head_movement"]
    assert (tot("fcfs"), tot("sstf"), tot("scan", "down"), tot("look", "down"), tot("cscan"), tot("clook")) == (640, 236, 236, 208, 382, 322)
    assert disk(q, 53, 199, "up", "fcfs").result["metrics"]["avg_seek_distance"] == 80.0

def test_lesson_memory_deadlock_fs_vm_numbers():
    ops = [{"op": "alloc", "pid": p, "size": s} for p, s in [("P1", 212), ("P2", 417), ("P3", 112), ("P4", 426)]]
    blocks = [100, 500, 200, 300, 600]
    fails = {s: mem(blocks, ops, s, "variable").result["metrics"]["failed_allocations"] for s in ("first_fit", "best_fit", "worst_fit")}
    assert fails == {"first_fit": 1, "best_fit": 0, "worst_fit": 1}
    assert mem(blocks, ops[:1], "first_fit", "fixed").result["metrics"]["internal_fragmentation"] == 288
    comp = mem([100] * 4, [{"op": "alloc", "pid": n, "size": 100} for n in "ABCD"] + [{"op": "free", "pid": "A"}, {"op": "free", "pid": "C"}, {"op": "alloc", "pid": "E", "size": 150}, {"op": "compact"}], "first_fit", "variable")
    assert comp.steps[-2].event == "alloc_failed" and comp.steps[-1].state["largest_hole"] == 200
    s = safety([3, 3, 2], [[0, 1, 0], [2, 0, 0], [3, 0, 2], [2, 1, 1], [0, 0, 2]], [[7, 5, 3], [3, 2, 2], [9, 0, 2], [2, 2, 2], [4, 3, 3]])
    assert s.result["sequence"] == ["P1", "P3", "P0", "P2", "P4"] and s.result["need"][0] == [7, 4, 3]
    ops = [{"op": "create", "path": "/a", "size": 3}, {"op": "create", "path": "/b", "size": 2}, {"op": "delete", "path": "/a"}, {"op": "create", "path": "/c", "size": 4}, {"op": "create", "path": "/d", "size": 8}]
    ev = {m: fs(16, m, ops).steps[-1].event for m in ("contiguous", "linked", "indexed")}
    assert ev == {"contiguous": "alloc_failed", "linked": "create", "indexed": "alloc_failed"}
    assert "needs 9 block(s) but only 8" in fs(16, "indexed", ops).steps[-1].explanation
    t = translate(1024, 8192, 8192, [0, 1024, 3072, 4096, 5120, 6144, 7168, 2500]).steps[-1].state
    assert (t["page"], t["offset"], t["frame"], t["physical"]) == (2, 452, 7, 7620) and divmod(3000, 1024) == (2, 952)
    th = thrashing(16, 4)
    assert th["thrashing_starts_at"] == 5 and next(r for r in th["rows"] if r["processes"] == 5)["frames_per_process"] == 3

# ---------------- quiz ----------------
def test_quiz_never_reveals_answers():
    for mid, _ in MODULES:
        for q in quiz.build(mid, "all", seed=42):
            assert set(q) <= {"id", "type", "level", "prompt", "options"}, q          # no answer / explanation / correct index field
            if q["type"] == "mcq":
                assert len(q["options"]) == 4

def test_quiz_has_questions_for_every_module_and_level():
    for mid, _ in MODULES:
        qs = quiz.build(mid, "all", seed=1)
        assert {q["level"] for q in qs} == {"beginner", "intermediate", "advanced"}
        assert sum(q["type"] == "mcq" for q in qs) == 3 and sum(q["type"] == "numeric" for q in qs) == 6

def test_generated_questions_are_deterministic_for_a_seed_and_differ_between_seeds():
    a, b = quiz.build("paging", "beginner", seed=5), quiz.build("paging", "beginner", seed=5)
    assert a == b
    assert [q["prompt"] for q in quiz.build("paging", "beginner", seed=6)] != [q["prompt"] for q in a]

def test_grading_recomputes_correct_answers_from_the_engines():
    for mid, _ in MODULES:
        qs = quiz.build(mid, "all", seed=99)
        answers = {}
        for q in qs:
            ch = quiz._check(q["id"])
            answers[q["id"]] = ch["answer"]
        g = quiz.grade([q["id"] for q in qs], answers)
        assert g["score"] == g["total"] == 9 and g["percent"] == 100.0, mid

def test_wrong_blank_and_garbage_answers_are_marked_wrong_with_explanations():
    qs = quiz.build("disk", "beginner", seed=3)
    ids = [q["id"] for q in qs]
    g = quiz.grade(ids, {ids[0]: "0", ids[1]: "abc"})
    assert g["score"] == 0 and all(r["explanation"] and r["correct_answer"] != "" for r in g["results"])
    assert g["by_level"]["beginner"]["total"] == len(ids)

def test_known_generated_answer_matches_independent_computation():
    qs = quiz.build("paging", "beginner", seed=11)
    n = next(q for q in qs if q["type"] == "numeric")
    seed = int(n["id"].split("|")[-1])
    import random
    r = random.Random(seed)
    refs = [r.randint(0, 5) for _ in range(10)]
    expected = paging(refs, 3, "fifo").result["metrics"]["faults"]
    assert str(refs) in n["prompt"] and quiz._check(n["id"])["answer"] == expected

def test_numeric_tolerance():
    qs = quiz.build("cpu", "beginner", seed=8)
    q = next(x for x in qs if x["type"] == "numeric")
    ans = float(quiz._check(q["id"])["answer"])
    assert quiz.grade([q["id"]], {q["id"]: f"{ans + 0.005}"})["score"] == 1
    assert quiz.grade([q["id"]], {q["id"]: f"{ans + 0.5}"})["score"] == 0

def test_tampered_or_invalid_ids_are_rejected():
    for bad in ["m|cpu|999", "m|paging|0", "n|cpu|beginner|abc", "n|nope|beginner|1", "../../etc/passwd", "x", "m|cpu|0; DROP TABLE"]:
        with pytest.raises(ValidationError):
            quiz.grade([bad], {})
    with pytest.raises(ValidationError):
        quiz.build("nope", "all")
    with pytest.raises(ValidationError):
        quiz.build("cpu", "expert")
    with pytest.raises(ValidationError):
        quiz.grade([], {})
