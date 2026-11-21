try:
    import pytest
except ImportError:
    from tests._shim import pytest
from app.engines.errors import ValidationError
from app.engines.fs.engine import simulate, compare

def C(path, size): return {"op": "create", "path": path, "size": size}
def last(tr): return tr.steps[-1]

FRAG = [C("/a", 3), C("/b", 2), {"op": "delete", "path": "/a"}, C("/c", 4)]       # 16-block disk

def test_contiguous_first_fit_run_and_fragmentation():
    tr = simulate(16, "contiguous", FRAG)
    files = {f["path"]: f["blocks"] for f in tr.result["files"]}
    assert files == {"/b": [3, 4], "/c": [5, 6, 7, 8]}
    m = tr.result["metrics"]
    assert m["free_blocks"] == 10 and m["largest_free_run"] == 7 and m["external_fragmentation_pct"] == 30.0

def test_same_operations_give_different_outcomes_per_allocation_method():
    ops = FRAG + [C("/d", 8)]                    # /d needs 8 blocks
    tr = simulate(16, "contiguous", ops)         # 10 blocks free but the largest run is 7
    assert last(tr).event == "alloc_failed" and "CONTIGUOUS" in last(tr).explanation and "external fragmentation" in last(tr).explanation
    assert last(simulate(16, "linked", ops)).event == "create"          # any free blocks will do
    ix = simulate(16, "indexed", ops)            # index blocks cost space: only 8 blocks are left, /d needs 8 + 1 index
    assert last(ix).event == "alloc_failed" and "needs 9 block(s) but only 8 are free" in last(ix).explanation

def test_linked_chain_and_fragments():
    tr = simulate(16, "linked", [C("/a", 2), C("/b", 1), C("/c", 2), {"op": "delete", "path": "/a"}, C("/big", 4)])
    big = next(f for f in tr.result["files"] if f["path"] == "/big")
    assert big["blocks"] == [0, 1, 5, 6]          # the freed blocks 0,1 then the next free ones
    s = last(tr).state
    assert s["next"]["0"] == 1 and s["next"]["1"] == 5 and s["next"]["6"] is None
    assert next(f for f in s["files_detail"] if f["path"] == "/big")["fragments"] == 2

def test_indexed_uses_one_index_block():
    tr = simulate(16, "indexed", [C("/f", 3)])
    f = tr.result["files"][0]
    assert f["index_block"] == 0 and f["blocks"] == [1, 2, 3]
    m = tr.result["metrics"]
    assert m["used_blocks"] == 4 and m["index_blocks"] == 1
    assert last(tr).state["roles"][:5] == ["index", "data", "data", "data", None]

def test_read_access_paths_differ_by_method():
    for m, word in [("contiguous", "direct"), ("linked", "pointer"), ("indexed", "index block")]:
        tr = simulate(16, m, [C("/f", 3), {"op": "read", "path": "/f"}])
        r = last(tr)
        assert r.event == "read" and word in r.explanation, m
    assert last(simulate(16, "indexed", [C("/f", 3), {"op": "read", "path": "/f"}])).state["access"] == [0, 1, 2, 3]
    assert last(simulate(16, "contiguous", [C("/f", 3), {"op": "read", "path": "/f"}])).state["disk_requests"] == [0, 1, 2]

def test_block_size_rounds_up():
    tr = simulate(16, "contiguous", [C("/f", 5)], block_size_kb=2)
    assert tr.result["files"][0]["blocks"] == [0, 1, 2]

def test_append_contiguous_blocked_by_neighbour_but_works_at_the_end():
    ops = [C("/a", 2), C("/b", 2), {"op": "append", "path": "/a", "size": 1}, {"op": "append", "path": "/b", "size": 1}]
    tr = simulate(16, "contiguous", ops)
    assert [s.event for s in tr.steps][-2:] == ["alloc_failed", "append"]
    assert next(f for f in tr.result["files"] if f["path"] == "/b")["blocks"] == [2, 3, 4]

def test_append_linked_updates_pointer():
    tr = simulate(16, "linked", [C("/a", 2), C("/b", 1), {"op": "append", "path": "/a", "size": 2}])
    a = next(f for f in tr.result["files"] if f["path"] == "/a")
    assert a["blocks"] == [0, 1, 3, 4] and last(tr).state["next"]["1"] == 3

def test_directories_and_errors():
    ops = [{"op": "mkdir", "path": "/docs"}, C("/docs/a.txt", 2), {"op": "delete", "path": "/docs"}, C("/nodir/x", 1), C("/docs/a.txt", 1),
           {"op": "delete", "path": "/docs/a.txt"}, {"op": "delete", "path": "/docs"}]
    tr = simulate(16, "contiguous", ops)
    assert [s.event for s in tr.steps][1:] == ["mkdir", "create", "error", "error", "error", "delete", "delete"]
    assert "not empty" in tr.steps[3].explanation and tr.result["metrics"]["free_blocks"] == 16 and tr.result["metrics"]["failed_operations"] == 3

def test_tree_structure():
    tr = simulate(16, "contiguous", [{"op": "mkdir", "path": "/d"}, C("/d/x", 1), C("/y", 1)])
    root = tr.result["tree"]
    assert [c["name"] for c in root["children"]] == ["d", "y"] and root["children"][0]["children"][0]["name"] == "x"

def test_blocks_are_conserved_and_owned_consistently():
    ops = FRAG + [C("/big", 3), {"op": "delete", "path": "/b"}, C("/e", 2)]
    for m in ("contiguous", "linked", "indexed"):
        tr = simulate(16, m, ops)
        for s in tr.steps:
            assert s.state["used_blocks"] + s.state["free_blocks"] == 16
            assert s.state["used_blocks"] == sum(1 for o in s.state["owners"] if o)

def test_paths_cannot_escape_the_virtual_disk():
    for bad in ["../etc/passwd", "/a/../b", "etc/passwd", "/a b", "/" + "x" * 40, "/a/./b", "/a;rm -rf", "/..", "C:\\Windows"]:
        with pytest.raises(ValidationError):
            simulate(16, "contiguous", [{"op": "mkdir", "path": bad}])

def test_compare_methods_same_ops():
    out = compare(16, FRAG + [C("/d", 8)], 1)
    fails = {r["label"]: r["metrics"]["failed_operations"] for r in out["runs"]}
    assert fails == {"Contiguous allocation": 1, "Linked allocation": 0, "Indexed allocation": 1}
    assert out["best_by_metric"]["failed_operations"] == ["Linked allocation"]

def test_validation():
    for args in [(2, "contiguous", [C("/a", 1)]), (16, "fat32", [C("/a", 1)]), (16, "linked", []), (16, "linked", [{"op": "format", "path": "/"}]), (16, "linked", [{"op": "create", "path": "/a"}])]:
        with pytest.raises(ValidationError):
            simulate(*args)
