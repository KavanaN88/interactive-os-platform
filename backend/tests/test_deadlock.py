try:
    import pytest
except ImportError:
    from tests._shim import pytest
from app.engines.errors import ValidationError
from app.engines.deadlock.engine import safety, request, detect, recover, rag, need_matrix

AV = [3, 3, 2]
AL = [[0, 1, 0], [2, 0, 0], [3, 0, 2], [2, 1, 1], [0, 0, 2]]
MX = [[7, 5, 3], [3, 2, 2], [9, 0, 2], [2, 2, 2], [4, 3, 3]]

def test_need_matrix():
    assert need_matrix(MX, AL)[0] == [7, 4, 3] and need_matrix(MX, AL)[1] == [1, 2, 2]

def test_banker_textbook_state_is_safe():
    tr = safety(AV, AL, MX)
    assert tr.result["safe"] and tr.result["sequence"] == ["P1", "P3", "P0", "P2", "P4"]
    # the sequence really is safe: replay it
    work = list(AV); need = tr.result["need"]
    for p in tr.result["sequence"]:
        i = int(p[1:]); assert all(n <= w for n, w in zip(need[i], work)); work = [w + a for w, a in zip(work, AL[i])]
    assert tr.steps[-1].event == "safe"

def test_trace_explains_skipped_processes():
    tr = safety(AV, AL, MX)
    assert "P0 (need [7, 4, 3] > work [3, 3, 2])" in tr.steps[1].explanation

def test_request_sequence_from_textbook():
    r = request(AV, AL, MX, 1, [1, 0, 2])
    assert r["granted"] and r["available"] == [2, 3, 0] and r["allocation"][1] == [3, 0, 2]
    av2, al2 = r["available"], r["allocation"]
    r4 = request(av2, al2, MX, 4, [3, 3, 0])
    assert not r4["granted"] and "must wait" in r4["reason"]
    r0 = request(av2, al2, MX, 0, [0, 2, 0])
    assert not r0["granted"] and "unsafe" in r0["reason"]

def test_request_exceeding_need_is_denied():
    r = request(AV, AL, MX, 1, [2, 0, 0])
    assert not r["granted"] and "exceeded" in r["reason"]

def test_unsafe_state_is_not_necessarily_deadlock():
    tr = safety([0], [[1], [1]], [[2], [2]])
    assert not tr.result["safe"] and tr.result["unfinished"] == ["P0", "P1"]
    assert "does not mean deadlock" in tr.steps[-1].explanation

DAV = [0, 0, 0]
DAL = [[0, 1, 0], [2, 0, 0], [3, 0, 3], [2, 1, 1], [0, 0, 2]]
DRQ = [[0, 0, 0], [2, 0, 2], [0, 0, 0], [1, 0, 0], [0, 0, 2]]

def test_detection_no_deadlock():
    d = detect(DAV, DAL, DRQ)
    assert not d.result["has_deadlock"] and d.result["sequence"] == ["P0", "P2", "P1", "P3", "P4"]

def test_detection_textbook_deadlock():
    rq = [r[:] for r in DRQ]; rq[2] = [0, 0, 1]
    d = detect(DAV, DAL, rq)
    assert d.result["deadlocked"] == ["P1", "P2", "P3", "P4"]
    assert d.steps[-1].event == "deadlock"

def test_recovery_terminates_largest_holder():
    rq = [r[:] for r in DRQ]; rq[2] = [0, 0, 1]
    tr = recover(DAV, DAL, rq)
    assert tr.result["terminated"] == ["P2"] and tr.result["final_available"] == [3, 0, 3]
    assert not detect(tr.result["final_available"], tr.result["final_allocation"], [[0, 0, 0]] * 5).result["has_deadlock"]

def test_recovery_when_no_deadlock():
    tr = recover(DAV, DAL, DRQ)
    assert tr.result["terminated"] == [] and tr.steps[-1].event == "recovered"

def test_rag_cycle_is_deadlock_for_single_instances():
    g = rag([0, 0], [[1, 0], [0, 1]], [[0, 1], [1, 0]])
    assert g["cycle"] and g["cycle_is_deadlock"]
    assert {(e["from"], e["to"], e["kind"]) for e in g["edges"]} == {("R0", "P0", "allocation"), ("R1", "P1", "allocation"),
                                                                    ("P0", "R1", "request"), ("P1", "R0", "request")}
    assert detect([0, 0], [[1, 0], [0, 1]], [[0, 1], [1, 0]]).result["deadlocked"] == ["P0", "P1"]

def test_rag_no_cycle_and_multi_instance_caution():
    assert rag([1, 0], [[0, 1], [0, 0]], [[0, 0], [1, 0]])["cycle"] == []
    g = rag([0, 0], [[1, 0], [0, 1]], [[0, 1], [1, 0]])
    g2 = rag([1, 0], [[1, 0], [0, 1]], [[0, 1], [1, 0]])     # R0 now has 2 instances
    assert g2["cycle"] and not g2["cycle_is_deadlock"] and "not sufficient" in g2["explanation"]

def test_validation():
    with pytest.raises(ValidationError, match="exceeds"):
        safety([1], [[3]], [[2]])
    with pytest.raises(ValidationError):
        safety([1, 1], [[1]], [[1]])
    with pytest.raises(ValidationError):
        safety([-1], [[0]], [[1]])
    with pytest.raises(ValidationError):
        request(AV, AL, MX, 9, [0, 0, 0])
