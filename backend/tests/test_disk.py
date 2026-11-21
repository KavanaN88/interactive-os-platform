try:
    import pytest
except ImportError:
    from tests._shim import pytest
from app.engines.errors import ValidationError
from app.engines.disk.engine import simulate, compare

Q = [98, 183, 37, 122, 14, 124, 65, 67]

def total(a, d="up", **kw):
    return simulate(Q, 53, 199, d, a, **kw).result["metrics"]["total_head_movement"]

def test_textbook_totals():
    assert total("fcfs") == 640
    assert total("sstf") == 236
    assert total("scan", "down") == 236
    assert total("cscan", "up") == 382
    assert total("look", "down") == 208
    assert total("clook", "up") == 322

def test_return_jump_can_be_excluded():
    assert total("cscan", "up", count_jump=False) == 183
    assert total("clook", "up", count_jump=False) == 153

def test_service_orders():
    assert simulate(Q, 53, 199, "up", "sstf").result["service_order"] == [65, 67, 37, 14, 98, 122, 124, 183]
    assert simulate(Q, 53, 199, "down", "scan").result["head_path"][:4] == [53, 37, 14, 0]
    assert simulate(Q, 53, 199, "up", "cscan").result["service_order"] == [65, 67, 98, 122, 124, 183, 14, 37]

def test_blueprint_sstf_example():
    tr = simulate([82, 170, 43, 140, 24, 16, 190], 50, 199, "up", "sstf")
    assert tr.result["service_order"] == [43, 24, 16, 82, 140, 170, 190]
    assert tr.result["metrics"]["total_head_movement"] == 208
    assert tr.result["metrics"]["avg_seek_distance"] == round(208 / 7, 4)

def test_scan_goes_to_boundary_but_look_does_not():
    assert simulate([60, 70], 50, 199, "up", "scan").result["metrics"]["total_head_movement"] == 149
    assert simulate([60, 70], 50, 199, "up", "look").result["metrics"]["total_head_movement"] == 20

def test_request_at_head_position_costs_zero():
    assert simulate([50], 50, 199, "up", "fcfs").result["metrics"]["total_head_movement"] == 0

def test_total_equals_sum_of_step_distances_and_every_request_serviced():
    for a in ["fcfs", "sstf", "scan", "cscan", "look", "clook"]:
        for d in ["up", "down"]:
            tr = simulate(Q, 53, 199, d, a)
            assert sum(s.state.get("distance", 0) for s in tr.steps) == tr.result["metrics"]["total_head_movement"], (a, d)
            assert sorted(tr.result["service_order"]) == sorted(Q), (a, d)

def test_head_at_boundaries():
    assert simulate([0, 199], 0, 199, "up", "scan").result["service_order"] == [0, 199]
    assert simulate([10], 199, 199, "down", "look").result["metrics"]["total_head_movement"] == 189

def test_compare():
    out = compare(Q, 53, 199, "up", ["fcfs", "sstf", "look"])
    assert out["best_by_metric"]["total_head_movement"] == ["SSTF"] or out["best_by_metric"]["total_head_movement"] == ["LOOK"]
    assert [r["metrics"]["total_head_movement"] for r in out["runs"]] == [640, 236, simulate(Q, 53, 199, "up", "look").result["metrics"]["total_head_movement"]]

def test_validation():
    with pytest.raises(ValidationError):
        simulate([200], 53, 199, "up", "fcfs")
    with pytest.raises(ValidationError):
        simulate([1], 500, 199, "up", "fcfs")
    with pytest.raises(ValidationError):
        simulate([1], 5, 199, "sideways", "fcfs")
    with pytest.raises(ValidationError):
        simulate([], 5, 199, "up", "fcfs")
    with pytest.raises(ValidationError):
        simulate([1], 5, 199, "up", "elevator")
