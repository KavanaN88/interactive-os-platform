"""API tests. Require fastapi + httpx (pip install -r requirements.txt). Not runnable by run_tests_offline.py."""
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
PROCS = [{"pid": "P1", "arrival": 0, "burst": 5}, {"pid": "P2", "arrival": 1, "burst": 3}, {"pid": "P3", "arrival": 2, "burst": 2}]

def test_health():
    assert client.get("/api/v1/health").json() == {"status": "ok"}

def test_simulate_fcfs_matches_engine():
    r = client.post("/api/v1/cpu/simulate", json={"algorithm": "fcfs", "processes": PROCS})
    assert r.status_code == 200
    g = [(s["pid"], s["start"], s["end"]) for s in r.json()["result"]["gantt"]]
    assert g == [("P1", 0, 5), ("P2", 5, 8), ("P3", 8, 10)]

def test_invalid_input_is_422():
    assert client.post("/api/v1/cpu/simulate", json={"algorithm": "rr", "processes": PROCS}).status_code == 422
    assert client.post("/api/v1/cpu/simulate", json={"algorithm": "nope", "processes": PROCS}).status_code == 422
    bad = [{"pid": "P1", "arrival": 0, "burst": 0}]
    assert client.post("/api/v1/cpu/simulate", json={"algorithm": "fcfs", "processes": bad}).status_code == 422

def test_compare():
    r = client.post("/api/v1/cpu/compare", json={"processes": PROCS, "configs": [{"algorithm": "fcfs"}, {"algorithm": "sjf"}]})
    assert r.status_code == 200 and len(r.json()["runs"]) == 2

def test_algorithms_catalog():
    assert len(client.get("/api/v1/cpu/algorithms").json()) == 8
