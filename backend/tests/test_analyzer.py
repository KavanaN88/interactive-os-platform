try:
    import pytest
except ImportError:
    from tests._shim import pytest
from app.engines.errors import ValidationError
from app.engines.analyzer.engine import catalog, compare, report, CATALOG

CPU = {"processes": [{"pid": "P1", "arrival": 0, "burst": 8}, {"pid": "P2", "arrival": 1, "burst": 4}, {"pid": "P3", "arrival": 2, "burst": 1}], "quantum": 2}
PAGING = {"refs": [7, 0, 1, 2, 0, 3, 0, 4, 2, 3, 0, 3, 2, 1, 2, 0, 1, 7, 0, 1], "frames": 3}
DISK = {"requests": [98, 183, 37, 122, 14, 124, 65, 67], "head": 53, "max_cylinder": 199, "direction": "up"}
MEM = {"blocks": [100, 500, 200, 300, 600], "ops": [{"op": "alloc", "pid": p, "size": s} for p, s in [("P1", 212), ("P2", 417), ("P3", 112), ("P4", 426)]], "mode": "variable"}
FS = {"total_blocks": 16, "ops": [{"op": "create", "path": "/a", "size": 3}, {"op": "create", "path": "/b", "size": 2}, {"op": "delete", "path": "/a"}, {"op": "create", "path": "/c", "size": 4}, {"op": "create", "path": "/d", "size": 8}]}
VM = {"page_size": 1024, "virtual_size": 8192, "physical_size": 2048, "addresses": [0, 1024, 0, 2048, 1024]}

def test_catalog_covers_six_categories_with_metrics():
    c = catalog()
    assert [x["module"] for x in c] == ["cpu", "paging", "disk", "memory", "fs", "vm"] and all(x["metrics"] and len(x["defaults"]) >= 2 for x in c)

def test_cpu_numbers_match_hand_calculation():
    r = compare("cpu", CPU, ["fcfs", "sjf", "rr"])
    assert {x["label"]: x["metrics"]["avg_waiting_time"] for x in r["runs"]}["First Come First Serve"] == 5.6667
    assert any("lowest average waiting time" in t for t in r["recommendations"])

def test_paging_recommendation_reports_gap_to_optimal():
    r = compare("paging", PAGING, ["fifo", "lru", "optimal"])
    txt = " ".join(r["recommendations"])
    assert "LRU had the fewest faults (12)" in txt and "3 fault(s) away" in txt and "Optimal" in txt

def test_disk_recommendation_percentage():
    r = compare("disk", DISK, ["fcfs", "sstf"])
    assert any("63.1% less movement than FCFS (640)" in t for t in r["recommendations"])      # (640-236)/640

def test_memory_recommendation_mentions_external_fragmentation():
    r = compare("memory", MEM, ["first_fit", "best_fit", "worst_fit"])
    txt = " ".join(r["recommendations"])
    assert "Best Fit placed the most processes" in txt and "external fragmentation" in txt

def test_fs_and_vm_compare_run():
    f = compare("fs", FS, ["contiguous", "linked", "indexed"])
    assert {x["label"]: x["metrics"]["failed_operations"] for x in f["runs"]}["Linked allocation"] == 0
    v = compare("vm", VM, ["fifo", "lru"])
    assert {x["label"]: x["metrics"]["page_faults"] for x in v["runs"]} == {"FIFO": 3, "LRU": 4} and v["best_by_metric"]["page_faults"] == ["FIFO"]

def test_every_run_uses_identical_input_and_never_declares_universal_winner():
    for m, w in [("cpu", CPU), ("paging", PAGING), ("disk", DISK), ("memory", MEM), ("fs", FS), ("vm", VM)]:
        r = compare(m, w, CATALOG[m]["defaults"])
        assert r["recommendations"][-1].startswith("These recommendations apply to THIS workload")
        assert all(set(c[0] for c in CATALOG[m]["metrics"]) <= set(run["metrics"]) for run in r["runs"]), m

def test_report_is_generated_from_real_results():
    md = report("paging", PAGING, ["fifo", "lru", "optimal"])["markdown"]
    assert md.startswith("# OS LAB Performance Report: Page Replacement")
    assert "| FIFO | 15 | 5 | 25.0 | 75.0 |" in md           # faults, hits, hit %, fault % straight from the engine
    assert "| LRU | 12 | 8 | 40.0 | 60.0 |" in md and "| Optimal | 9 | 11 | 55.0 | 45.0 |" in md
    assert "## Recommendations" in md and '"frames": 3' in md and "**Faults**: Optimal" in md

def test_validation():
    for args in [("nope", {}, ["a", "b"]), ("paging", PAGING, ["fifo"]), ("paging", PAGING, ["fifo", "bogus"]), ("paging", {"refs": [1]}, ["fifo", "lru"]), ("cpu", "x", ["fcfs", "sjf"])]:
        with pytest.raises(ValidationError):
            compare(*args)
