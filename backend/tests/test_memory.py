try:
    import pytest
except ImportError:
    from tests._shim import pytest
from app.engines.errors import ValidationError
from app.engines.memory.engine import simulate, compare

BLOCKS = [100, 500, 200, 300, 600]
PROCS = [{"op": "alloc", "pid": p, "size": s} for p, s in [("P1", 212), ("P2", 417), ("P3", 112), ("P4", 426)]]

def placed(tr):
    return {s["pid"]: s["start"] for s in tr.result["segments"] if s["pid"]}

def test_first_fit_textbook():
    tr = simulate(BLOCKS, PROCS, "first_fit", "variable")
    assert placed(tr) == {"P1": 100, "P2": 1100, "P3": 312}
    m = tr.result["metrics"]
    assert m["failed_allocations"] == 1 and m["external_failures"] == 1   # 959 KB free, but no hole >= 426

def test_best_fit_textbook_places_everything():
    tr = simulate(BLOCKS, PROCS, "best_fit", "variable")
    assert placed(tr) == {"P1": 800, "P2": 100, "P3": 600, "P4": 1100}
    assert tr.result["metrics"]["failed_allocations"] == 0

def test_worst_fit_textbook():
    tr = simulate(BLOCKS, PROCS, "worst_fit", "variable")
    assert placed(tr) == {"P1": 1100, "P2": 100, "P3": 1312}
    assert tr.result["metrics"]["failed_allocations"] == 1

def test_blueprint_first_fit_example():
    tr = simulate([100, 500, 200, 300], [{"op": "alloc", "pid": "P", "size": 180}], "first_fit", "variable")
    step = tr.steps[1]
    assert step.event == "alloc" and step.state["chosen_start"] == 100
    assert step.state["examined"] == [{"start": 0, "size": 100, "fits": False}, {"start": 100, "size": 500, "fits": True}]
    assert [s["size"] for s in tr.result["segments"]] == [100, 180, 320, 200, 300]   # 320 KB remainder

def test_fixed_partitions_have_internal_fragmentation():
    tr = simulate(BLOCKS, PROCS, "first_fit", "fixed")
    m = tr.result["metrics"]
    assert placed(tr) == {"P1": 100, "P2": 1100, "P3": 600}   # whole 500 / 600 / 200 partitions, no splitting
    assert m["internal_fragmentation"] == 288 + 183 + 88
    assert m["failed_allocations"] == 1
    assert len(tr.result["segments"]) == 5                # partitions never split

def test_free_coalesces_adjacent_holes():
    ops = [{"op": "alloc", "pid": n, "size": 100} for n in "ABC"] + [{"op": "free", "pid": "A"}, {"op": "free", "pid": "B"},
                                                                       {"op": "alloc", "pid": "D", "size": 150}]
    tr = simulate([100, 100, 100], ops, "first_fit", "variable")
    assert tr.steps[-1].event == "alloc" and placed(tr)["D"] == 0

def test_external_fragmentation_then_compaction_fixes_it():
    ops = ([{"op": "alloc", "pid": n, "size": 100} for n in "ABCD"] + [{"op": "free", "pid": "A"}, {"op": "free", "pid": "C"},
           {"op": "alloc", "pid": "E", "size": 150}, {"op": "compact"}, {"op": "alloc", "pid": "E", "size": 150}])
    tr = simulate([100] * 4, ops, "first_fit", "variable")
    ev = [s.event for s in tr.steps]
    assert ev[-3:] == ["alloc_failed", "compact", "alloc"]
    failed = tr.steps[-3]
    assert failed.state["external_fragmentation_pct"] == 50.0 and "external fragmentation" in failed.explanation
    comp = tr.steps[-2]
    assert comp.state["moved"] == [{"pid": "B", "from": 100, "to": 0}, {"pid": "D", "from": 300, "to": 100}]
    assert [s["size"] for s in comp.state["segments"] if s["pid"] is None] == [200]

def test_memory_is_conserved_after_every_step():
    ops = PROCS + [{"op": "free", "pid": "P1"}, {"op": "compact"}, {"op": "alloc", "pid": "P4", "size": 426}]
    for strat in ["first_fit", "best_fit", "worst_fit"]:
        for tr in [simulate(BLOCKS, ops, strat, "variable")]:
            for s in tr.steps:
                assert sum(x["size"] for x in s.state["segments"]) == 1700
                starts = [x["start"] for x in s.state["segments"]]
                assert starts == sorted(starts)

def test_bad_operations_are_reported_not_crashed():
    tr = simulate([100], [{"op": "free", "pid": "X"}, {"op": "alloc", "pid": "A", "size": 50}, {"op": "alloc", "pid": "A", "size": 10}], "first_fit", "variable")
    assert [s.event for s in tr.steps] == ["init", "error", "alloc", "error"]

def test_total_failure_is_not_external_fragmentation():
    tr = simulate([100], [{"op": "alloc", "pid": "A", "size": 500}], "first_fit", "variable")
    assert tr.result["metrics"]["failed_allocations"] == 1 and tr.result["metrics"]["external_failures"] == 0

def test_compare_strategies_same_input():
    out = compare(BLOCKS, PROCS, "variable")
    fails = {r["label"]: r["metrics"]["failed_allocations"] for r in out["runs"]}
    assert fails == {"First Fit": 1, "Best Fit": 0, "Worst Fit": 1}
    assert out["best_by_metric"]["failed_allocations"] == ["Best Fit"]

def test_validation():
    with pytest.raises(ValidationError):
        simulate([100], [{"op": "compact"}], "first_fit", "fixed")
    with pytest.raises(ValidationError):
        simulate([0], [], "first_fit", "variable")
    with pytest.raises(ValidationError):
        simulate([100], [{"op": "alloc", "pid": "A", "size": 0}], "first_fit", "variable")
    with pytest.raises(ValidationError):
        simulate([100], [{"op": "explode"}], "first_fit", "variable")
    with pytest.raises(ValidationError):
        simulate([100], [], "next_fit", "variable")
