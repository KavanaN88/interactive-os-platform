try:
    import pytest
except ImportError:
    from tests._shim import pytest
from app.engines.errors import ValidationError
from app.engines.sync.scenarios import run_scenario, catalog

def go(name, **kw):
    return run_scenario(name, kw)

def test_race_condition_two_threads_one_increment_loses_an_update():
    tr = go("race_condition", threads=2, increments=1, synchronized=False, quantum=1)
    assert tr.result["shared"]["counter"] == 1 and tr.result["lost_updates"] == 1 and tr.result["race_detected"]
    assert [s.explanation for s in tr.steps[1:5]] == ["T1 reads counter = 0", "T2 reads counter = 0", "T1 computes 1 in a register", "T2 computes 1 in a register"]

def test_mutex_removes_the_race_for_every_time_slice():
    for q in (1, 2, 3, 7):
        tr = go("race_condition", threads=3, increments=4, synchronized=True, quantum=q)
        assert tr.result["shared"]["counter"] == 12 and not tr.result["race_detected"], q

def test_race_disappears_when_time_slice_is_long_enough():
    tr = go("race_condition", threads=2, increments=3, synchronized=False, quantum=100)
    assert tr.result["shared"]["counter"] == 6          # each thread runs to completion: interleaving decides the bug

def test_runs_are_deterministic():
    a = go("race_condition", threads=3, increments=3, synchronized=False, quantum=2).to_dict()
    assert a == go("race_condition", threads=3, increments=3, synchronized=False, quantum=2).to_dict()

def test_critical_section_mutual_exclusion():
    ok = go("critical_section", threads=4, synchronized=True, quantum=1)
    assert ok.result["metrics"]["max_threads_inside"] == 1 and ok.result["violations"] == 0
    bad = go("critical_section", threads=4, synchronized=False, quantum=1)
    assert bad.result["metrics"]["max_threads_inside"] > 1 and bad.result["violations"] > 0

def test_blocked_thread_is_queued_and_woken_in_fifo_order():
    tr = go("critical_section", threads=3, synchronized=True, quantum=1)
    ev = [s.event for s in tr.steps]
    assert "blocked" in ev and ev.count("signal") == 3
    woken = [s.explanation.split("; ")[1].split(" ")[0] for s in tr.steps if s.event == "signal" and "woken" in s.explanation]
    assert woken == ["T2", "T3"]

def test_binary_semaphore_orders_consumer_after_producer():
    tr = go("binary_semaphore", work_steps=3, quantum=1)
    assert tr.result["shared"]["consumer_started_after_work"] is True
    assert [s.event for s in tr.steps][1] == "blocked"

def test_counting_semaphore_never_exceeds_pool():
    tr = go("counting_semaphore", threads=6, resources=2, hold=3, quantum=1)
    assert tr.result["shared"]["max_in_use"] == 2 and not tr.result["unfinished"]
    for s in tr.steps:
        assert s.state["shared"]["in_use"] <= 2 and s.state["sems"]["pool"]["value"] >= 0

def test_producer_consumer_synchronized_is_correct():
    for q in (1, 2, 5):
        tr = go("producer_consumer", buffer=3, producers=2, consumers=2, items=6, synchronized=True, quantum=q)
        sh = tr.result["shared"]
        assert sorted(sh["consumed"]) == sorted(sh["produced"]) and len(sh["consumed"]) == 12 and tr.result["violations"] == 0
        assert all(len(s.state["shared"]["buffer"]) <= 3 for s in tr.steps) and not tr.result["deadlock"], q

def test_producer_consumer_unsynchronized_overflows_with_small_buffer():
    tr = go("producer_consumer", buffer=2, producers=1, consumers=1, items=6, synchronized=False, quantum=4)
    assert tr.result["violations"] > 0 and tr.result["metrics"]["lost_items"] > 0

def test_producer_consumer_rejects_uneven_split():
    with pytest.raises(ValidationError, match="equally"):
        go("producer_consumer", producers=1, consumers=2, items=5)

def test_readers_writers_exclusion_holds():
    tr = go("readers_writers", readers=4, writers=2, synchronized=True, quantum=1)
    assert tr.result["violations"] == 0 and not tr.result["unfinished"] and tr.result["shared"]["version"] == 2
    assert tr.result["metrics"]["max_concurrent_readers"] >= 2           # readers really do overlap

def test_readers_writers_without_sync_violates():
    assert go("readers_writers", readers=3, writers=2, synchronized=False, quantum=1).result["violations"] > 0

def test_dining_philosophers_naive_deadlocks_with_fine_interleaving():
    tr = go("dining_philosophers", philosophers=5, meals=2, strategy="naive", quantum=1)
    assert tr.result["deadlock"] and tr.steps[-1].event == "deadlock" and "circular wait" in tr.result["explanation"]
    assert all(s == "blocked" for s in tr.steps[-1].state["threads"].values())

def test_dining_philosophers_fixes_prevent_deadlock():
    for strat in ("ordered", "waiter"):
        for q in (1, 2, 3):
            tr = go("dining_philosophers", philosophers=5, meals=3, strategy=strat, quantum=q)
            assert not tr.result["deadlock"] and tr.result["metrics"]["meals_eaten"] == 15, (strat, q)

def test_naive_philosophers_survive_long_time_slices():
    tr = go("dining_philosophers", philosophers=5, meals=2, strategy="naive", quantum=50)
    assert not tr.result["deadlock"] and tr.result["metrics"]["meals_eaten"] == 10

def test_no_fork_is_held_by_two_philosophers():
    tr = go("dining_philosophers", philosophers=5, meals=2, strategy="ordered", quantum=1)
    for s in tr.steps:
        for name, sem in s.state["sems"].items():
            assert len(sem["holders"]) <= 1 or name == "waiter"

def test_catalog_and_validation():
    assert len(catalog()) == 7 and all(c["params"] for c in catalog())
    with pytest.raises(ValidationError):
        run_scenario("nope", {})
    with pytest.raises(ValidationError):
        run_scenario("race_condition", {"threads": 99})
    with pytest.raises(ValidationError):
        run_scenario("dining_philosophers", {"strategy": "random"})
    with pytest.raises(ValidationError):
        run_scenario("race_condition", {"synchronized": "yes"})
