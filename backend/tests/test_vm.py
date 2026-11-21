try:
    import pytest
except ImportError:
    from tests._shim import pytest
from app.engines.errors import ValidationError
from app.engines.vm.engine import translate, compare, working_set, thrashing

def T(addrs, ps=1024, vs=8192, pm=8192, **kw):
    return translate(ps, vs, pm, addrs, **kw)

def test_blueprint_translation_page2_to_frame7():
    # touch 7 other pages first so page 2 lands in frame 7, then translate 2500
    tr = T([0, 1024, 3072, 4096, 5120, 6144, 7168, 2500])
    s = tr.steps[-1].state
    assert (s["page"], s["offset"], s["frame"], s["physical"]) == (2, 452, 7, 7 * 1024 + 452) and s["physical"] == 7620
    assert tr.steps[-1].event == "page_fault"

def test_first_access_faults_then_tlb_hit():
    tr = T([2500, 2600], pm=2048)
    assert [s.event for s in tr.steps][1:] == ["page_fault", "tlb_hit"]
    assert [s.state["physical"] for s in tr.steps[1:]] == [452, 552]
    assert any("PAGE FAULT" in a for a in tr.steps[1].state["actions"])

def test_tlb_miss_with_resident_page_uses_page_table():
    tr = T([0, 1024, 2048, 0], tlb_size=2)                     # page 0 evicted from the 2-entry TLB, still resident in memory
    assert [s.event for s in tr.steps][1:] == ["page_fault", "page_fault", "page_fault", "tlb_miss"]
    assert tr.steps[-1].state["frame"] == 0 and tr.result["metrics"]["page_faults"] == 3

def test_tlb_lru_vs_fifo():
    addrs = [0, 1024, 0, 2048, 0]
    assert T(addrs, tlb_size=2, tlb_policy="lru").result["metrics"]["tlb_hits"] == 2
    assert T(addrs, tlb_size=2, tlb_policy="fifo").result["metrics"]["tlb_hits"] == 1

def test_fifo_beats_lru_on_this_string_and_counts_match_hand_calculation():
    addrs = [0, 1024, 0, 2048, 1024]                           # pages 0,1,0,2,1 with 2 frames
    assert T(addrs, pm=2048, replacement="fifo").result["metrics"]["page_faults"] == 3
    assert T(addrs, pm=2048, replacement="lru").result["metrics"]["page_faults"] == 4

def test_eviction_invalidates_the_stale_tlb_entry():
    tr = T([0, 1024, 0], pm=1024, tlb_size=4)                  # one frame: page 0 is evicted, its TLB entry must go
    assert [s.event for s in tr.steps][1:] == ["page_fault"] * 3 and tr.result["metrics"]["tlb_hits"] == 0
    assert any("stale TLB entry" in a for a in tr.steps[2].state["actions"])

def test_invalid_addresses_are_rejected_without_changing_memory():
    tr = T([-1, 8192, 100])
    assert [s.event for s in tr.steps][1:] == ["invalid", "invalid", "page_fault"]
    assert tr.result["metrics"]["invalid_accesses"] == 2 and tr.steps[1].state["frames"] == [None] * 8

def test_effective_access_time_matches_formula():
    assert T([0], tlb_size=0).result["metrics"]["effective_access_time_ns"] == 100 + 8_000_000 + 100
    assert T([0, 1], tlb_size=4).result["metrics"]["effective_access_time_ns"] == (10 + 100 + 8_000_000 + 100 + 10 + 100) / 2
    assert T([0, 1], tlb_size=0, costs={"fault_ns": 0}).result["metrics"]["effective_access_time_ns"] == (200 + 200) / 2

def test_frames_and_page_table_stay_consistent():
    tr = T([i * 1024 for i in (0, 1, 2, 3, 0, 4, 1, 5)], pm=3072, replacement="lru")
    for s in tr.steps:
        resident = {int(p): e["frame"] for p, e in s.state["page_table"].items() if e["valid"]}
        assert len(set(resident.values())) == len(resident)
        assert all(s.state["frames"][f] == p for p, f in resident.items())
        assert all(s.state["frames"][f] == p for p, f in s.state["tlb"])

def test_compare_policies():
    out = compare(1024, 8192, 2048, [0, 1024, 0, 2048, 1024])
    assert {r["label"]: r["metrics"]["page_faults"] for r in out["runs"]} == {"FIFO": 3, "LRU": 4}
    assert out["best_by_metric"]["page_faults"] == ["FIFO"]

def test_working_set_window():
    w = working_set([1, 2, 1, 3, 4], 3)
    assert [r["size"] for r in w["rows"]] == [1, 2, 2, 3, 3] and w["peak"] == 3 and w["average"] == 2.2
    assert w["rows"][3]["working_set"] == [1, 2, 3]

def test_thrashing_curve_rises_then_collapses_when_frames_drop_below_working_set():
    t = thrashing(16, 4)
    u = {r["processes"]: r["cpu_utilization"] for r in t["rows"]}
    assert u[1] < u[2] == u[3] == u[4] == 100.0
    assert t["thrashing_starts_at"] == 5 and t["peak_processes"] == 2
    assert u[5] < 0.1 * u[4] and all(u[n] <= u[5] for n in range(6, 13))
    assert next(r for r in t["rows"] if r["processes"] == 5)["frames_per_process"] == 3
    assert "thrashing" in t["explanation"]

def test_no_thrashing_when_memory_is_plentiful():
    t = thrashing(256, 4, max_processes=8)
    assert t["thrashing_starts_at"] is None and "no thrashing" in t["explanation"]

def test_thrashing_is_deterministic():
    assert thrashing(16, 4) == thrashing(16, 4)

def test_validation():
    for kw in [dict(ps=0), dict(vs=512), dict(pm=512), dict(tlb_size=99), dict(replacement="mru"), dict(tlb_policy="random")]:
        with pytest.raises(ValidationError):
            translate(kw.get("ps", 1024), kw.get("vs", 8192), kw.get("pm", 4096), [0], kw.get("tlb_size", 4), kw.get("tlb_policy", "lru"), kw.get("replacement", "lru"))
    with pytest.raises(ValidationError):
        T([1.5])
    with pytest.raises(ValidationError):
        T([])
    with pytest.raises(ValidationError):
        working_set([1], 0)
    with pytest.raises(ValidationError):
        thrashing(0, 4)
