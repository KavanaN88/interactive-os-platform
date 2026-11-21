try:
    import pytest
except ImportError:
    from tests._shim import pytest
from app.engines.errors import ValidationError
from app.engines.process.engine import simulate, ipc, threads_demo

def P(pid, arrival, bursts, **kw):
    return {"pid": pid, "arrival": arrival, "bursts": bursts, **kw}

def events(tr, pid=None):
    return [(s.event, s.state.get("pid")) for s in tr.steps if pid is None or s.state.get("pid") == pid]

def test_single_process_full_lifecycle():
    tr = simulate([P("A", 0, [3])], 2)
    assert [e for e, _ in events(tr)] == ["create", "admit", "dispatch", "preempt", "dispatch", "terminate"]
    assert [s.state["transition"] for s in tr.steps if s.event in ("create", "admit", "dispatch", "terminate")][:2] == [[None, "new"], ["new", "ready"]]
    assert tr.result["processes"][0]["completion"] == 3 and tr.result["metrics"]["context_switches"] == 0

def test_io_burst_moves_process_through_waiting():
    tr = simulate([P("A", 0, [2, 3, 1])], 5)
    assert [e for e, _ in events(tr)] == ["create", "admit", "dispatch", "io_request", "io_complete", "dispatch", "terminate"]
    a = tr.result["processes"][0]
    assert a["cpu_time"] == 3 and a["io_time"] == 3 and a["completion"] == 6          # 2 run + 3 io + 1 run
    assert tr.result["transitions"]["running->waiting"] == 1 and tr.result["transitions"]["waiting->ready"] == 1

def test_round_robin_two_processes_and_context_switches():
    tr = simulate([P("A", 0, [4]), P("B", 0, [4])], 2)
    segs = [(s["state"], s["start"], s["end"]) for s in tr.result["timeline"]["B"]]
    assert segs == [("new", 0, 0), ("ready", 0, 2), ("running", 2, 4), ("ready", 4, 6), ("running", 6, 8)] or segs[-1] == ("running", 6, 8)
    assert tr.result["metrics"]["context_switches"] == 3          # A->B, B->A, A->B
    assert {p["pid"]: p["completion"] for p in tr.result["processes"]} == {"A": 6, "B": 8}

def test_dispatch_reports_saved_and_restored_context():
    tr = simulate([P("A", 0, [4]), P("B", 0, [4])], 2)
    d = [s for s in tr.steps if s.event == "dispatch" and s.state["context_switch"]][0]
    cs = d.state["context_switch"]
    assert cs["saved"]["pid"] == "A" and cs["saved"]["regs"]["PC"] == 0x1000 + 8
    assert cs["restored"]["pid"] == "B" and cs["restored"]["regs"]["PC"] == 0x1000

def test_idle_gap_until_arrival():
    tr = simulate([P("A", 0, [1]), P("B", 5, [1])], 2)
    assert {p["pid"]: p["completion"] for p in tr.result["processes"]} == {"A": 1, "B": 6}
    assert tr.result["metrics"]["cpu_utilization"] == round(100 * 2 / 6, 2)

def test_parent_child_tree():
    tr = simulate([P("init", 0, [1]), P("shell", 0, [1], parent="init"), P("ls", 1, [1], parent="shell"), P("cat", 1, [1], parent="shell")], 2)
    assert tr.result["tree"] == [{"pid": "init", "children": [{"pid": "shell", "children": [{"pid": "ls", "children": []}, {"pid": "cat", "children": []}]}]}]
    assert any("fork" in s.explanation for s in tr.steps if s.event == "create" and s.state["pid"] == "ls")

def test_every_process_terminates_and_time_is_accounted():
    procs = [P("A", 0, [3, 2, 2]), P("B", 1, [2, 4, 1]), P("C", 2, [5])]
    tr = simulate(procs, 2)
    for p in tr.result["processes"]:
        assert p["cpu_time"] + p["io_time"] + p["ready_time"] == p["turnaround"]
        assert p["cpu_time"] == sum(procs[["A", "B", "C"].index(p["pid"])]["bursts"][0::2])
    assert tr.steps[-1].event == "terminate"

def test_state_transitions_are_legal():
    legal = {(None, "new"), ("new", "ready"), ("ready", "running"), ("running", "ready"), ("running", "waiting"), ("waiting", "ready"), ("running", "terminated")}
    tr = simulate([P("A", 0, [3, 2, 2]), P("B", 1, [2, 4, 1]), P("C", 2, [5])], 2)
    assert all(tuple(s.state["transition"]) in legal for s in tr.steps)

def test_never_two_running_at_once():
    tr = simulate([P("A", 0, [3, 2, 2]), P("B", 0, [2, 4, 1])], 1)
    for s in tr.steps:
        assert sum(1 for p in s.state["processes"].values() if p["state"] == "running") <= 1

def test_validation():
    for bad, q in [([], 2), ([P("A", 0, [1, 2])], 2), ([P("A", 0, [0])], 2), ([P("A", -1, [1])], 2), ([P("A", 0, [1]), P("A", 0, [1])], 2),
                   ([P("B", 0, [1], parent="A")], 2), ([P("A", 5, [1]), P("B", 1, [1], parent="A")], 2), ([P("a b", 0, [1])], 2), ([P("A", 0, [1])], 0)]:
        with pytest.raises(ValidationError):
            simulate(bad, q)

def test_pipe_blocks_when_full_and_resumes():
    ops = [{"by": "W", "op": "send", "data": i} for i in (1, 2, 3)] + [{"by": "R", "op": "recv"}]
    tr = ipc("pipe", ops, 2)
    assert [s.event for s in tr.steps] == ["init", "send", "send", "blocked", "recv", "unblocked"]
    assert tr.steps[-1].state["buffer"] == [2, 3] and tr.result["still_blocked"] == []

def test_reader_blocks_on_empty_queue_until_message_arrives():
    tr = ipc("message_queue", [{"by": "R", "op": "recv"}, {"by": "S", "op": "send", "data": "hi"}], 3)
    assert [s.event for s in tr.steps] == ["init", "blocked", "send", "unblocked"] and tr.steps[-1].state["buffer"] == []

def test_fifo_order_preserved():
    tr = ipc("pipe", [{"by": "W", "op": "send", "data": x} for x in "abc"] + [{"by": "R", "op": "recv"}] * 3, 5)
    assert [s.explanation.split("'")[1] for s in tr.steps if s.event == "recv"] == ["a", "b", "c"]

def test_shared_memory_lost_update_is_flagged():
    ops = [{"by": "A", "op": "write", "key": "x", "data": 1}, {"by": "B", "op": "write", "key": "x", "data": 2}, {"by": "A", "op": "read", "key": "x"}, {"by": "A", "op": "read", "key": "y"}]
    tr = ipc("shared_memory", ops)
    assert [s.event for s in tr.steps][1:] == ["write", "violation", "read", "violation"] and tr.result["metrics"]["violations"] == 2

def test_ipc_validation():
    with pytest.raises(ValidationError):
        ipc("telepathy", [{"by": "A", "op": "send", "data": 1}])
    with pytest.raises(ValidationError):
        ipc("pipe", [{"by": "A", "op": "write", "data": 1}])
    with pytest.raises(ValidationError):
        ipc("shared_memory", [{"by": "A", "op": "write", "data": 1}])

def test_threads_share_heap_but_not_stack():
    tr = threads_demo(3, 4)
    assert tr.result["shared"]["heap_counter"] == 12
    assert [v["local_sum"] for v in tr.result["stacks"].values()] == [10, 10, 10]
    assert len({v["SP"] for v in tr.result["stacks"].values()}) == 3
