from app.db.seed_data import MODULES, ROLES, algorithm_rows
from app.engines.cpu import ALGORITHMS


def test_ten_modules_unique_slugs():
    slugs = [m[0] for m in MODULES]
    assert len(slugs) == 10 and len(set(slugs)) == 10

def test_roles():
    assert ROLES == ["student", "administrator", "guest"]

def test_cpu_algorithms_seeded_as_implemented():
    rows = [r for r in algorithm_rows() if r[0] == "cpu_scheduling"]
    assert [r[1] for r in rows] == ALGORITHMS and all(r[5] for r in rows)

def test_unbuilt_modules_not_marked_implemented():
    assert all(not r[5] for r in algorithm_rows() if r[0] != "cpu_scheduling")

def test_no_duplicate_algorithm_slug_within_module():
    seen = set()
    for m, a, *_ in algorithm_rows():
        assert (m, a) not in seen
        seen.add((m, a))
