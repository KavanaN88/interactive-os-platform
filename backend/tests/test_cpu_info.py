from app.engines.cpu import ALGORITHMS
from app.engines.cpu.info import algorithm_catalog

def test_every_algorithm_has_catalog_entry():
    cat = algorithm_catalog()
    assert [c["id"] for c in cat] == ALGORITHMS
    for c in cat:
        assert c["description"] and len(c["rules"]) >= 2

def test_input_flags():
    by = {c["id"]: c for c in algorithm_catalog()}
    assert by["rr"]["needs_quantum"] and not by["fcfs"]["needs_quantum"]
    assert by["priority_p"]["needs_priority"] and by["mlq"]["needs_queue"]
    assert by["mlfq"]["needs_levels"] and not by["mlfq"]["needs_queue"]
