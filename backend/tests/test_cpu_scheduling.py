try:
    import pytest
except ImportError:  # offline sandbox
    from tests._shim import pytest

from app.engines.cpu import Process as P, ValidationError, simulate, compare


def gantt(tr):
    return [(s["pid"], s["start"], s["end"]) for s in tr.result["gantt"]]

def per(tr, pid):
    return next(x for x in tr.result["processes"] if x["pid"] == pid)

def m(tr):
    return tr.result["metrics"]


# ---------- FCFS ----------
def test_fcfs_blueprint_example():
    tr = simulate([P("P1", 0, 5), P("P2", 1, 3), P("P3", 2, 2)], "fcfs")
    assert gantt(tr) == [("P1", 0, 5), ("P2", 5, 8), ("P3", 8, 10)]
    assert [per(tr, p)["completion"] for p in ("P1", "P2", "P3")] == [5, 8, 10]
    assert [per(tr, p)["turnaround"] for p in ("P1", "P2", "P3")] == [5, 7, 8]
    assert [per(tr, p)["waiting"] for p in ("P1", "P2", "P3")] == [0, 4, 6]
    assert m(tr)["avg_waiting_time"] == 3.3333
    assert m(tr)["cpu_utilization"] == 100.0
    assert m(tr)["context_switches"] == 2

def test_fcfs_idle_period_and_utilization():
    tr = simulate([P("P1", 0, 2), P("P2", 5, 1)], "fcfs")
    assert gantt(tr) == [("P1", 0, 2), (None, 2, 5), ("P2", 5, 6)]
    assert m(tr)["cpu_utilization"] == 50.0
    assert tr.result["idle_periods"] == [{"pid": None, "start": 2, "end": 5}]
    assert per(tr, "P2")["waiting"] == 0

def test_fcfs_starts_after_initial_idle():
    tr = simulate([P("P1", 3, 2)], "fcfs")
    assert gantt(tr) == [(None, 0, 3), ("P1", 3, 5)]
    assert m(tr)["cpu_utilization"] == 40.0

def test_simultaneous_arrivals_use_input_order():
    tr = simulate([P("B", 0, 2), P("A", 0, 2)], "fcfs")
    assert gantt(tr) == [("B", 0, 2), ("A", 2, 4)]


# ---------- SJF / SRTF (classic 4-process set) ----------
SET = [P("P1", 0, 7), P("P2", 2, 4), P("P3", 4, 1), P("P4", 5, 4)]

def test_sjf_non_preemptive():
    tr = simulate(SET, "sjf")
    assert gantt(tr) == [("P1", 0, 7), ("P3", 7, 8), ("P2", 8, 12), ("P4", 12, 16)]
    assert [per(tr, p)["waiting"] for p in ("P1", "P2", "P3", "P4")] == [0, 6, 3, 7]
    assert m(tr)["avg_waiting_time"] == 4.0

def test_srtf_preemptive():
    tr = simulate(SET, "srtf")
    assert gantt(tr) == [("P1", 0, 2), ("P2", 2, 4), ("P3", 4, 5), ("P2", 5, 7), ("P4", 7, 11), ("P1", 11, 16)]
    assert [per(tr, p)["waiting"] for p in ("P1", "P2", "P3", "P4")] == [9, 1, 0, 2]
    assert m(tr)["avg_waiting_time"] == 3.0
    assert any(s.event == "preempt" for s in tr.steps)

def test_srtf_tie_keeps_running_process():
    # P2 arrives with remaining == P1's remaining: no pointless preemption
    tr = simulate([P("P1", 0, 4), P("P2", 2, 2)], "srtf")
    assert gantt(tr) == [("P1", 0, 4), ("P2", 4, 6)]


# ---------- Round Robin ----------
def test_rr_simultaneous_arrival():
    tr = simulate([P("P1", 0, 4), P("P2", 0, 3), P("P3", 0, 2)], "rr", quantum=2)
    assert gantt(tr) == [("P1", 0, 2), ("P2", 2, 4), ("P3", 4, 6), ("P1", 6, 8), ("P2", 8, 9)]
    assert [per(tr, p)["completion"] for p in ("P1", "P2", "P3")] == [8, 9, 6]
    assert [per(tr, p)["waiting"] for p in ("P1", "P2", "P3")] == [4, 6, 4]
    assert [per(tr, p)["response"] for p in ("P1", "P2", "P3")] == [0, 2, 4]

def test_rr_new_arrival_queues_before_preempted_process():
    tr = simulate([P("P1", 0, 5), P("P2", 1, 3)], "rr", quantum=2)
    assert gantt(tr) == [("P1", 0, 2), ("P2", 2, 4), ("P1", 4, 6), ("P2", 6, 7), ("P1", 7, 8)]

def test_rr_large_quantum_equals_fcfs():
    ps = [P("P1", 0, 5), P("P2", 1, 3), P("P3", 2, 2)]
    assert gantt(simulate(ps, "rr", quantum=100)) == gantt(simulate(ps, "fcfs"))

def test_rr_single_process_has_no_context_switch():
    assert m(simulate([P("P1", 0, 5)], "rr", quantum=2))["context_switches"] == 0


# ---------- Priority ----------
def test_priority_non_preemptive():
    tr = simulate([P("P1", 0, 4, 2), P("P2", 1, 3, 1), P("P3", 2, 2, 3)], "priority_np")
    assert gantt(tr) == [("P1", 0, 4), ("P2", 4, 7), ("P3", 7, 9)]

def test_priority_preemptive():
    tr = simulate([P("P1", 0, 4, 3), P("P2", 1, 2, 1), P("P3", 2, 1, 2)], "priority_p")
    assert gantt(tr) == [("P1", 0, 1), ("P2", 1, 3), ("P3", 3, 4), ("P1", 4, 7)]

def test_priority_tie_breaks_by_arrival():
    # P3 (pri 1, arr 0) and P2 (pri 1, arr 1) tie on priority; earlier arrival wins. P1 (pri 5) is last.
    tr = simulate([P("P1", 0, 2, 5), P("P2", 1, 2, 1), P("P3", 0, 2, 1)], "priority_np")
    assert [g[0] for g in gantt(tr)] == ["P3", "P2", "P1"]

# ---------- Multilevel ----------
def test_mlq_higher_queue_preempts_lower():
    tr = simulate([P("P1", 0, 5, queue=1), P("P2", 2, 2, queue=0)], "mlq", levels=[None, None])
    assert gantt(tr) == [("P1", 0, 2), ("P2", 2, 4), ("P1", 4, 7)]

def test_mlq_round_robin_inside_queue():
    tr = simulate([P("A", 0, 3, queue=0), P("B", 0, 3, queue=0)], "mlq", levels=[1, None])
    assert gantt(tr)[:4] == [("A", 0, 1), ("B", 1, 2), ("A", 2, 3), ("B", 3, 4)]

def test_mlq_rejects_missing_queue():
    with pytest.raises(ValidationError, match="queue 3"):
        simulate([P("A", 0, 3, queue=3)], "mlq", levels=[2, None])

def test_mlfq_demotes_after_full_quantum():
    tr = simulate([P("P1", 0, 7)], "mlfq", levels=[2, 4, 8])
    assert gantt(tr) == [("P1", 0, 7)]
    assert [s.event for s in tr.steps].count("demote") == 2

def test_mlfq_short_job_overtakes_demoted_long_job():
    tr = simulate([P("P1", 0, 6), P("P2", 1, 1)], "mlfq", levels=[2, 4])
    assert gantt(tr) == [("P1", 0, 2), ("P2", 2, 3), ("P1", 3, 7)]
    assert per(tr, "P2")["response"] == 1


# ---------- Invariants across all algorithms ----------
ALL = [("fcfs", {}), ("sjf", {}), ("srtf", {}), ("rr", {"quantum": 3}),
       ("priority_np", {}), ("priority_p", {}), ("mlq", {}), ("mlfq", {})]
MIX = [P("A", 0, 6, 2, 0), P("B", 1, 3, 1, 1), P("C", 2, 8, 3, 0), P("D", 12, 2, 1, 1), P("E", 30, 4, 2, 0)]

def test_invariants_every_algorithm():
    for algo, kw in ALL:
        tr = simulate(MIX, algo, **kw)
        busy = sum(e - s for p, s, e in gantt(tr) if p)
        assert busy == sum(p.burst for p in MIX), algo           # every unit of work executed exactly once
        for p in tr.result["processes"]:
            assert p["turnaround"] == p["completion"] - p["arrival"], algo
            assert p["waiting"] == p["turnaround"] - p["burst"] and p["waiting"] >= 0, algo
            assert p["response"] >= 0 and p["start"] >= p["arrival"], algo
        segs = tr.result["gantt"]
        assert all(a["end"] == b["start"] for a, b in zip(segs, segs[1:])), algo   # no gaps/overlaps
        assert segs[-1]["end"] == tr.result["metrics"]["makespan"], algo

def test_simulation_is_deterministic():
    a = simulate(MIX, "srtf").to_dict()
    b = simulate(MIX, "srtf").to_dict()
    assert a == b


# ---------- Validation ----------
def test_validation_errors():
    with pytest.raises(ValidationError, match="Duplicate"):
        simulate([P("P1", 0, 1), P("P1", 1, 1)], "fcfs")
    with pytest.raises(ValidationError, match="burst"):
        simulate([P("P1", 0, 0)], "fcfs")
    with pytest.raises(ValidationError, match="arrival"):
        simulate([P("P1", -1, 2)], "fcfs")
    with pytest.raises(ValidationError, match="quantum"):
        simulate([P("P1", 0, 2)], "rr")
    with pytest.raises(ValidationError, match="Unknown"):
        simulate([P("P1", 0, 2)], "magic")
    with pytest.raises(ValidationError, match="At least one"):
        simulate([], "fcfs")
    with pytest.raises(ValidationError, match="too large"):
        simulate([P("P1", 0, 60_000)], "fcfs")
    with pytest.raises(ValidationError, match="integer"):
        simulate([P("P1", 0, 2.5)], "fcfs")


# ---------- Trace + comparison ----------
def test_trace_pagination_is_bounded():
    tr = simulate(MIX, "rr", quantum=1)
    page = tr.page(offset=0, limit=5)
    assert len(page["steps"]) == 5 and page["total_steps"] == len(tr.steps)
    assert tr.page(offset=len(tr.steps), limit=5)["steps"] == []

def test_compare_uses_identical_input_and_real_metrics():
    ps = [P("P1", 0, 8), P("P2", 1, 4), P("P3", 2, 1)]
    out = compare(ps, [{"algorithm": "fcfs"}, {"algorithm": "sjf"}, {"algorithm": "rr", "quantum": 2}])
    solo = {r["label"]: simulate(ps, r["config"]["algorithm"], r["config"].get("quantum")).result["metrics"]
            for r in out["runs"]}
    for r in out["runs"]:
        assert r["metrics"] == solo[r["label"]]
    # hand-computed average waiting times: FCFS 17/3, SJF 14/3, RR(q=2) 11/3
    waits = {r["label"]: r["metrics"]["avg_waiting_time"] for r in out["runs"]}
    assert waits == {"First Come First Serve": 5.6667,
                     "Shortest Job First (non-preemptive)": 4.6667,
                     "Round Robin (q=2)": 3.6667}
    assert out["best_by_metric"]["avg_waiting_time"] == ["Round Robin (q=2)"]
    assert any("FCFS made short jobs wait" in n for n in out["explanation"])
    assert any("tie on CPU utilization" in n for n in out["explanation"])

def test_compare_needs_two_distinct_configs():
    ps = [P("P1", 0, 2)]
    with pytest.raises(ValidationError):
        compare(ps, [{"algorithm": "fcfs"}])
    with pytest.raises(ValidationError, match="distinct"):
        compare(ps, [{"algorithm": "fcfs"}, {"algorithm": "fcfs"}])


# ---------- bounded traces (performance) ----------
def _big():
    import random
    r = random.Random(7)
    return [P(f"P{i}", r.randint(0, 200), r.randint(1, 150)) for i in range(60)]

def test_trace_is_bounded_but_results_are_identical_to_a_full_run():
    ps = _big()
    full = simulate(ps, "rr", quantum=1, max_steps=10 ** 9)
    capped = simulate(ps, "rr", quantum=1)                      # default cap
    none = simulate(ps, "rr", quantum=1, max_steps=0)
    assert len(full.steps) > 5000 and len(capped.steps) == 5000 and len(none.steps) == 0
    assert capped.total_steps == none.total_steps == full.total_steps == len(full.steps)
    for t in (capped, none):
        assert t.result == full.result                          # Gantt, per-process table and metrics unchanged
    assert capped.steps == full.steps[:5000]                    # the recorded part is exactly the beginning of the full trace

def test_small_runs_record_every_step():
    tr = simulate([P("A", 0, 3), P("B", 1, 2)], "fcfs")
    assert tr.total_steps == len(tr.steps)

def test_compare_does_not_build_traces():
    import time
    ps = _big()
    t = time.perf_counter()
    compare(ps, [{"algorithm": a} for a in ("fcfs", "sjf", "srtf", "priority_np", "priority_p")] + [{"algorithm": "rr", "quantum": 1}])
    assert time.perf_counter() - t < 2.0                        # was ~1.5 s for 100 processes before the fix
