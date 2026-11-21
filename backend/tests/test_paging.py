try:
    import pytest
except ImportError:
    from tests._shim import pytest
from app.engines.errors import ValidationError
from app.engines.paging.engine import simulate, compare, belady

CLASSIC = [7, 0, 1, 2, 0, 3, 0, 4, 2, 3, 0, 3, 2, 1, 2, 0, 1, 7, 0, 1]
BELADY = [1, 2, 3, 4, 1, 2, 5, 1, 2, 3, 4, 5]

def faults(refs, f, a):
    return simulate(refs, f, a).result["metrics"]["faults"]

def test_classic_textbook_fault_counts():
    assert faults(CLASSIC, 3, "fifo") == 15
    assert faults(CLASSIC, 3, "lru") == 12
    assert faults(CLASSIC, 3, "optimal") == 9

def test_optimal_never_worse_than_others():
    o = faults(CLASSIC, 3, "optimal")
    assert all(o <= faults(CLASSIC, 3, a) for a in ["fifo", "lru", "lfu", "clock"])

def test_blueprint_fifo_example():
    tr = simulate([1, 2, 3, 1, 4], 3, "fifo")
    assert [s.event for s in tr.steps] == ["fault", "fault", "fault", "hit", "replace"]
    assert tr.steps[-1].state["frames"] == [4, 2, 3] and tr.steps[-1].state["victim"] == 1
    assert tr.result["metrics"] == {"hits": 1, "faults": 4, "hit_ratio": 20.0, "fault_ratio": 80.0, "references": 5}
    assert tr.result["timeline"] == ["F", "F", "F", "H", "F"]

def test_frames_fill_in_order_and_hits_leave_frames_unchanged():
    tr = simulate([1, 2, 1], 3, "lru")
    assert tr.steps[0].state["frames"] == [1, None, None]
    assert tr.steps[1].state["frames"] == [1, 2, None]
    assert tr.steps[2].state["frames"] == [1, 2, None] and tr.steps[2].event == "hit"

def test_lru_uses_recency_not_arrival():
    tr = simulate([1, 2, 3, 1, 4], 3, "lru")           # 1 was just used, so 2 is the LRU victim
    assert tr.steps[-1].state["victim"] == 2 and tr.steps[-1].state["frames"] == [1, 4, 3]

def test_lfu_evicts_lowest_count():
    tr = simulate([1, 2, 3, 1, 2, 4], 3, "lfu")
    assert tr.steps[-1].state["victim"] == 3 and tr.steps[-1].state["frames"] == [1, 2, 4]

def test_lfu_tie_breaks_by_oldest():
    tr = simulate([1, 2, 3, 4], 3, "lfu")              # all counts equal -> oldest (1)
    assert tr.steps[-1].state["victim"] == 1

def test_optimal_evicts_page_never_used_again():
    tr = simulate([1, 2, 3, 4, 1, 2], 3, "optimal")    # 3 never used again
    assert tr.steps[3].state["victim"] == 3

def test_clock_second_chance():
    tr = simulate([1, 2, 3, 4], 3, "clock")
    s = tr.steps[-1].state
    assert s["frames"] == [4, 2, 3] and s["ref_bits"] == [1, 0, 0] and s["pointer"] == 1
    tr = simulate([1, 2, 3, 4, 1], 3, "clock")
    assert tr.steps[-1].state["frames"] == [4, 1, 3] and tr.steps[-1].state["victim"] == 2

def test_clock_hit_sets_reference_bit():
    tr = simulate([1, 2, 3, 4, 2, 5], 3, "clock")      # after 4: bits [1,0,0]; hit on 2 sets its bit -> 5 skips 2
    assert tr.steps[4].state["ref_bits"] == [1, 1, 0]
    assert tr.steps[5].state["victim"] == 3

def test_beladys_anomaly_with_fifo():
    assert faults(BELADY, 3, "fifo") == 9 and faults(BELADY, 4, "fifo") == 10
    b = belady(BELADY, "fifo", 5)
    assert b["anomaly"] and b["anomalies"][0] == {"from_frames": 3, "to_frames": 4, "faults_from": 9, "faults_to": 10}

def test_lru_and_optimal_have_no_anomaly():
    assert not belady(BELADY, "lru", 7)["anomaly"]
    assert not belady(BELADY, "optimal", 7)["anomaly"]

def test_hits_plus_faults_equals_references_all_algorithms():
    for a in ["fifo", "lru", "optimal", "lfu", "clock"]:
        m = simulate(CLASSIC, 4, a).result["metrics"]
        assert m["hits"] + m["faults"] == len(CLASSIC)

def test_single_frame_and_more_frames_than_pages():
    assert faults([1, 1, 2, 2], 1, "fifo") == 2
    assert faults([1, 2, 1, 2], 5, "lru") == 2

def test_compare_matches_individual_runs():
    out = compare(CLASSIC, 3, ["fifo", "lru", "optimal"])
    assert [r["metrics"]["faults"] for r in out["runs"]] == [15, 12, 9]
    assert out["best_by_metric"]["faults"] == ["Optimal"]

def test_validation():
    for bad in [([], 3, "fifo"), ([1, -1], 3, "fifo"), ([1], 0, "fifo"), ([1], 99, "fifo"), ([1], 3, "nope"), ([1.5], 3, "fifo")]:
        with pytest.raises(ValidationError):
            simulate(*bad)
    with pytest.raises(ValidationError):
        compare([1], 2, ["fifo"])
