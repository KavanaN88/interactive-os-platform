"""API tests. Need fastapi + httpx + sqlalchemy installed (pip install -r requirements.txt)."""
from fastapi.testclient import TestClient
from app.main import app

c = TestClient(app)
P = "/api/v1"

def test_paging_simulate_and_belady():
    refs = [7, 0, 1, 2, 0, 3, 0, 4, 2, 3, 0, 3, 2, 1, 2, 0, 1, 7, 0, 1]
    r = c.post(f"{P}/page-replacement/simulate", json={"refs": refs, "frames": 3, "algorithm": "lru"})
    assert r.status_code == 200 and r.json()["result"]["metrics"]["faults"] == 12
    b = c.post(f"{P}/page-replacement/belady", json={"refs": [1, 2, 3, 4, 1, 2, 5, 1, 2, 3, 4, 5], "algorithm": "fifo", "max_frames": 5})
    assert b.json()["anomaly"] is True

def test_disk_simulate_and_compare():
    body = {"requests": [98, 183, 37, 122, 14, 124, 65, 67], "head": 53, "max_cylinder": 199, "direction": "up", "algorithm": "fcfs"}
    assert c.post(f"{P}/disk/simulate", json=body).json()["result"]["metrics"]["total_head_movement"] == 640
    body.pop("algorithm"); body["algorithms"] = ["fcfs", "sstf"]
    assert len(c.post(f"{P}/disk/compare", json=body).json()["runs"]) == 2

def test_memory_simulate():
    body = {"blocks": [100, 500, 200, 300, 600], "strategy": "best_fit", "mode": "variable",
            "ops": [{"op": "alloc", "pid": "P1", "size": 212}, {"op": "compact"}]}
    r = c.post(f"{P}/memory/simulate", json=body)
    assert r.status_code == 200 and r.json()["steps"][1]["event"] == "alloc"

def test_deadlock_endpoints():
    st = {"available": [3, 3, 2], "allocation": [[0, 1, 0], [2, 0, 0], [3, 0, 2], [2, 1, 1], [0, 0, 2]],
          "maximum": [[7, 5, 3], [3, 2, 2], [9, 0, 2], [2, 2, 2], [4, 3, 3]]}
    assert c.post(f"{P}/deadlock/safety", json=st).json()["result"]["safe"] is True
    assert c.post(f"{P}/deadlock/request", json={**st, "pid": 1, "request": [1, 0, 2]}).json()["granted"] is True
    d = {"available": [0, 0], "allocation": [[1, 0], [0, 1]], "request": [[0, 1], [1, 0]]}
    assert c.post(f"{P}/deadlock/detect", json=d).json()["result"]["has_deadlock"] is True
    assert c.post(f"{P}/deadlock/graph", json=d).json()["cycle_is_deadlock"] is True

def test_bad_input_is_422():
    assert c.post(f"{P}/page-replacement/simulate", json={"refs": [1], "frames": 3, "algorithm": "nope"}).status_code == 422
    assert c.post(f"{P}/disk/simulate", json={"requests": [500], "head": 1, "max_cylinder": 199, "algorithm": "fcfs"}).status_code == 422


def test_phase5_endpoints():
    r = c.post(f"{P}/process/simulate", json={"processes": [{"pid": "A", "arrival": 0, "bursts": [3]}], "quantum": 2})
    assert r.status_code == 200 and r.json()["result"]["metrics"]["makespan"] == 3
    assert len(c.get(f"{P}/sync/scenarios").json()) == 7
    r = c.post(f"{P}/sync/run", json={"scenario": "race_condition", "params": {"threads": 2, "increments": 1, "synchronized": False, "quantum": 1}})
    assert r.json()["result"]["shared"]["counter"] == 1
    r = c.post(f"{P}/filesystem/simulate", json={"total_blocks": 16, "method": "contiguous", "ops": [{"op": "create", "path": "/a", "size": 3}]})
    assert r.json()["result"]["files"][0]["blocks"] == [0, 1, 2]
    r = c.post(f"{P}/virtual-memory/translate", json={"page_size": 1024, "virtual_size": 8192, "physical_size": 2048, "addresses": [2500]})
    assert r.json()["steps"][1]["state"]["physical"] == 452
    assert c.post(f"{P}/virtual-memory/thrashing", json={"total_frames": 16, "working_set_size": 4}).json()["thrashing_starts_at"] == 5
    r = c.post(f"{P}/analyzer/compare", json={"module": "paging", "workload": {"refs": [1, 2, 3, 1, 4], "frames": 3}, "algorithms": ["fifo", "lru"]})
    assert r.status_code == 200 and r.json()["recommendations"]
    assert c.post(f"{P}/analyzer/report", json={"module": "paging", "workload": {"refs": [1, 2, 3, 1, 4], "frames": 3}, "algorithms": ["fifo", "lru"]}).json()["markdown"].startswith("# OS LAB")
    sid = "api-test-session"
    assert c.post(f"{P}/terminal/exec", json={"session_id": sid, "command": "os-info"}).json()["ok"] is True
    assert c.post(f"{P}/terminal/exec", json={"session_id": sid, "command": "ls; rm -rf /"}).json()["ok"] is False
    assert len(c.get(f"{P}/learn/modules").json()) == 10 and len(c.get(f"{P}/learn/topics", params={"module": "cpu"}).json()) == 3
    assert c.get(f"{P}/learn/topics/cpu-basics").json()["level"] == "beginner" and c.get(f"{P}/learn/topics/nope").status_code == 404
    qs = c.get(f"{P}/quiz/paging", params={"level": "beginner"}).json()["questions"]
    assert qs and all("answer" not in q for q in qs)
    g = c.post(f"{P}/quiz/grade", json={"question_ids": [q["id"] for q in qs], "answers": {}}).json()
    assert g["score"] == 0 and g["total"] == len(qs)

def test_phase5_bad_input_is_422():
    assert c.post(f"{P}/sync/run", json={"scenario": "nope"}).status_code == 422
    assert c.post(f"{P}/filesystem/simulate", json={"total_blocks": 16, "method": "contiguous", "ops": [{"op": "mkdir", "path": "../etc"}]}).status_code == 422
    assert c.post(f"{P}/quiz/grade", json={"question_ids": ["../../etc/passwd"], "answers": {}}).status_code == 422
