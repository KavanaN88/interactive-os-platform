"""Classic synchronisation problems built on the kernel. Each scenario is deterministic for the same parameters."""
from __future__ import annotations

from app.engines.errors import ValidationError
from app.engines.sync.kernel import run

Q = {"name": "quantum", "label": "Operations per time slice", "type": "int", "default": 1, "min": 1, "max": 100}
SYNC = {"name": "synchronized", "label": "Use synchronization", "type": "bool", "default": True}

SCHEMAS = {
    "race_condition": {"title": "Race Condition (shared counter)", "description":
        "Threads increment a shared counter with separate read, add and write steps. Without a lock, updates are lost.",
        "params": [{"name": "threads", "label": "Threads", "type": "int", "default": 2, "min": 2, "max": 6},
                   {"name": "increments", "label": "Increments per thread", "type": "int", "default": 3, "min": 1, "max": 10}, SYNC, Q]},
    "critical_section": {"title": "Critical Section & Mutex", "description":
        "Threads enter a critical section. A mutex guarantees only one thread is inside at a time.",
        "params": [{"name": "threads", "label": "Threads", "type": "int", "default": 3, "min": 2, "max": 6}, SYNC, Q]},
    "binary_semaphore": {"title": "Binary Semaphore (signalling)", "description":
        "A semaphore starting at 0 makes the Consumer wait until the Producer signals that its work is finished.",
        "params": [{"name": "work_steps", "label": "Producer work steps", "type": "int", "default": 3, "min": 1, "max": 8}, Q]},
    "counting_semaphore": {"title": "Counting Semaphore (resource pool)", "description":
        "A pool of identical resources: at most N threads may use them at the same time.",
        "params": [{"name": "threads", "label": "Threads", "type": "int", "default": 5, "min": 2, "max": 8},
                   {"name": "resources", "label": "Resources in the pool", "type": "int", "default": 2, "min": 1, "max": 6},
                   {"name": "hold", "label": "Ticks each thread holds a resource", "type": "int", "default": 2, "min": 1, "max": 5}, Q]},
    "producer_consumer": {"title": "Producer–Consumer (bounded buffer)", "description":
        "Producers fill a bounded buffer and consumers empty it, using empty/full semaphores and a mutex.",
        "params": [{"name": "buffer", "label": "Buffer capacity", "type": "int", "default": 3, "min": 1, "max": 8},
                   {"name": "producers", "label": "Producers", "type": "int", "default": 1, "min": 1, "max": 3},
                   {"name": "consumers", "label": "Consumers", "type": "int", "default": 1, "min": 1, "max": 3},
                   {"name": "items", "label": "Items per producer", "type": "int", "default": 5, "min": 1, "max": 10}, SYNC, Q]},
    "readers_writers": {"title": "Readers–Writers (reader preference)", "description":
        "Many readers may read together, but a writer needs exclusive access. Reader preference can starve writers.",
        "params": [{"name": "readers", "label": "Readers", "type": "int", "default": 3, "min": 1, "max": 5},
                   {"name": "writers", "label": "Writers", "type": "int", "default": 2, "min": 1, "max": 3}, SYNC, Q]},
    "dining_philosophers": {"title": "Dining Philosophers", "description":
        "Philosophers need two forks to eat. 'naive' can deadlock; 'ordered' (resource hierarchy) and 'waiter' cannot.",
        "params": [{"name": "philosophers", "label": "Philosophers", "type": "int", "default": 5, "min": 2, "max": 8},
                   {"name": "meals", "label": "Meals each", "type": "int", "default": 2, "min": 1, "max": 4},
                   {"name": "strategy", "label": "Strategy", "type": "choice", "default": "naive", "options": ["naive", "ordered", "waiter"]}, Q]},
}


def _race(p):
    sh = {"counter": 0, "expected": p["threads"] * p["increments"]}
    sy = p["synchronized"]

    def mk(i):
        def g():
            for _ in range(p["increments"]):
                if sy:
                    yield ("wait", "mutex")
                tmp = sh["counter"]
                yield ("do", f"T{i} reads counter = {tmp}")
                tmp += 1
                yield ("do", f"T{i} computes {tmp} in a register")
                sh["counter"] = tmp
                yield ("do", f"T{i} writes counter = {tmp}")
                if sy:
                    yield ("signal", "mutex")
        return g
    tr = run("race_condition", [(f"T{i}", mk(i)) for i in range(1, p["threads"] + 1)], {"mutex": 1} if sy else {}, sh, p["quantum"], input=p)
    lost = sh["expected"] - sh["counter"]
    tr.result.update(lost_updates=lost, race_detected=lost > 0, metrics={**tr.result["metrics"], "final_value": sh["counter"], "expected_value": sh["expected"], "lost_updates": lost})
    tr.result["explanation"] = (f"Final counter = {sh['counter']} but {sh['expected']} was expected: {lost} update(s) were lost to a race condition." if lost
                                else f"Final counter = {sh['counter']}, exactly as expected" + (" because the mutex made each read-modify-write atomic." if sy else " (this interleaving happened not to collide; try a different time slice)."))
    return tr


def _critical(p):
    sh = {"in_cs": 0, "max_in_cs": 0}
    sy = p["synchronized"]

    def mk(i):
        def g():
            if sy:
                yield ("wait", "mutex")
            sh["in_cs"] += 1
            sh["max_in_cs"] = max(sh["max_in_cs"], sh["in_cs"])
            bad = sh["in_cs"] > 1
            yield ("do", f"T{i} ENTERS the critical section ({sh['in_cs']} thread(s) inside)" + (" — mutual exclusion violated!" if bad else ""), "violation" if bad else None) if bad else ("do", f"T{i} ENTERS the critical section ({sh['in_cs']} inside)")
            yield ("do", f"T{i} works on the shared resource")
            sh["in_cs"] -= 1
            yield ("do", f"T{i} LEAVES the critical section")
            if sy:
                yield ("signal", "mutex")
        return g
    tr = run("critical_section", [(f"T{i}", mk(i)) for i in range(1, p["threads"] + 1)], {"mutex": 1} if sy else {}, sh, p["quantum"], input=p)
    tr.result["metrics"]["max_threads_inside"] = sh["max_in_cs"]
    tr.result["explanation"] = f"At most {sh['max_in_cs']} thread(s) were inside at once" + (": mutual exclusion held." if sh["max_in_cs"] == 1 else ": mutual exclusion was violated.")
    return tr


def _binary(p):
    sh = {"work_done": 0, "consumer_started_after_work": None}

    def prod():
        for k in range(p["work_steps"]):
            sh["work_done"] += 1
            yield ("do", f"Producer finishes work step {k + 1}/{p['work_steps']}")
        yield ("signal", "ready")

    def cons():
        yield ("wait", "ready")
        sh["consumer_started_after_work"] = sh["work_done"] == p["work_steps"]
        yield ("do", f"Consumer proceeds (producer completed {sh['work_done']}/{p['work_steps']} steps)")
    tr = run("binary_semaphore", [("Consumer", cons), ("Producer", prod)], {"ready": 0}, sh, p["quantum"], input=p)
    tr.result["explanation"] = "The semaphore started at 0, so the Consumer blocked until the Producer signalled: the work was always finished first."
    return tr


def _counting(p):
    sh = {"in_use": 0, "max_in_use": 0}

    def mk(i):
        def g():
            yield ("wait", "pool")
            sh["in_use"] += 1
            sh["max_in_use"] = max(sh["max_in_use"], sh["in_use"])
            for k in range(p["hold"]):
                yield ("do", f"T{i} uses a resource ({sh['in_use']}/{p['resources']} in use) tick {k + 1}/{p['hold']}")
            sh["in_use"] -= 1
            yield ("signal", "pool")
        return g
    tr = run("counting_semaphore", [(f"T{i}", mk(i)) for i in range(1, p["threads"] + 1)], {"pool": p["resources"]}, sh, p["quantum"], input=p)
    tr.result["metrics"]["max_in_use"] = sh["max_in_use"]
    tr.result["explanation"] = f"The pool of {p['resources']} was never exceeded (peak use {sh['max_in_use']})."
    return tr


def _pc(p):
    total = p["producers"] * p["items"]
    if total % p["consumers"]:
        raise ValidationError(f"{total} items cannot be shared equally by {p['consumers']} consumers; change the numbers")
    per_c, cap, sy = total // p["consumers"], p["buffer"], p["synchronized"]
    sh = {"buffer": [], "produced": [], "consumed": [], "lost_items": 0, "peak": 0}

    def prod(i):
        def g():
            for k in range(p["items"]):
                item = f"P{i}-{k + 1}"
                if sy:
                    yield ("wait", "empty")
                    yield ("wait", "mutex")
                if not sy and len(sh["buffer"]) >= cap:
                    sh["lost_items"] += 1
                    yield ("do", f"Producer {i} tries to insert {item} but the buffer is FULL: item lost (overflow)", "violation")
                    continue
                sh["buffer"].append(item)
                sh["produced"].append(item)
                sh["peak"] = max(sh["peak"], len(sh["buffer"]))
                yield ("do", f"Producer {i} inserts {item} (buffer {len(sh['buffer'])}/{cap})")
                if sy:
                    yield ("signal", "mutex")
                    yield ("signal", "full")
        return g

    def cons(i):
        def g():
            for _ in range(per_c):
                if sy:
                    yield ("wait", "full")
                    yield ("wait", "mutex")
                if not sy and not sh["buffer"]:
                    yield ("do", f"Consumer {i} reads from an EMPTY buffer: garbage data (underflow)", "violation")
                    continue
                item = sh["buffer"].pop(0)
                sh["consumed"].append(item)
                yield ("do", f"Consumer {i} removes {item} (buffer {len(sh['buffer'])}/{cap})")
                if sy:
                    yield ("signal", "mutex")
                    yield ("signal", "empty")
        return g
    threads = [(f"Producer{i}", prod(i)) for i in range(1, p["producers"] + 1)] + [(f"Consumer{i}", cons(i)) for i in range(1, p["consumers"] + 1)]
    tr = run("producer_consumer", threads, {"empty": cap, "full": 0, "mutex": 1} if sy else {}, sh, p["quantum"], input=p)
    tr.result["metrics"].update(items_produced=len(sh["produced"]), items_consumed=len(sh["consumed"]), peak_buffer=sh["peak"], lost_items=sh["lost_items"])
    tr.result["explanation"] = (f"Synchronized: {len(sh['consumed'])} of {total} items were consumed, none lost, and the buffer never exceeded {cap}." if sy
                                else f"Unsynchronized: {tr.result['violations']} violation(s) (overflow/underflow); {sh['lost_items']} item(s) lost.")
    return tr


def _rw(p):
    sh = {"readcount": 0, "active_readers": [], "writer": None, "version": 0, "max_readers": 0}
    sy = p["synchronized"]

    def reader(i):
        def g():
            if sy:
                yield ("wait", "rmutex")
            sh["readcount"] += 1
            if sy:
                if sh["readcount"] == 1:
                    yield ("wait", "wrt")
                yield ("signal", "rmutex")
            sh["active_readers"].append(i)
            sh["max_readers"] = max(sh["max_readers"], len(sh["active_readers"]))
            bad = sh["writer"] is not None
            for k in range(2):
                yield ("do", f"Reader{i} reads version {sh['version']} ({len(sh['active_readers'])} reader(s) active)" + (" WHILE a writer is writing!" if bad else ""), "violation" if bad else None)
            sh["active_readers"].remove(i)
            if sy:
                yield ("wait", "rmutex")
            sh["readcount"] -= 1
            if sy:
                if sh["readcount"] == 0:
                    yield ("signal", "wrt")
                yield ("signal", "rmutex")
        return g

    def writer(i):
        def g():
            if sy:
                yield ("wait", "wrt")
            sh["writer"] = i
            bad = bool(sh["active_readers"])
            for k in range(2):
                yield ("do", f"Writer{i} writes (step {k + 1}/2)" + (" WHILE readers are reading!" if bad else ""), "violation" if bad else None)
            sh["version"] += 1
            sh["writer"] = None
            if sy:
                yield ("signal", "wrt")
        return g
    threads = [(f"Reader{i}", reader(i)) for i in range(1, p["readers"] + 1)] + [(f"Writer{i}", writer(i)) for i in range(1, p["writers"] + 1)]
    tr = run("readers_writers", threads, {"rmutex": 1, "wrt": 1} if sy else {}, sh, p["quantum"], input=p)
    tr.result["metrics"]["max_concurrent_readers"] = sh["max_readers"]
    tr.result["explanation"] = (f"Up to {sh['max_readers']} readers read at the same time, writers always had exclusive access (no violations). With reader preference a steady stream of readers could starve writers."
                                if sy and not tr.result["violations"] else f"{tr.result['violations']} violation(s): readers and writers overlapped.")
    return tr


def _dp(p):
    n, strat = p["philosophers"], p["strategy"]
    sh = {"meals": {f"P{i}": 0 for i in range(n)}}
    sems = {f"fork{i}": 1 for i in range(n)}
    if strat == "waiter":
        sems["waiter"] = n - 1

    def mk(i):
        l, r = i, (i + 1) % n
        first, second = (min(l, r), max(l, r)) if strat == "ordered" else (l, r)

        def g():
            for _ in range(p["meals"]):
                yield ("do", f"P{i} is thinking")
                if strat == "waiter":
                    yield ("wait", "waiter")
                yield ("wait", f"fork{first}")
                yield ("wait", f"fork{second}")
                sh["meals"][f"P{i}"] += 1
                yield ("do", f"P{i} EATS with forks {first} and {second} (meal {sh['meals'][f'P{i}']})")
                yield ("signal", f"fork{first}")
                yield ("signal", f"fork{second}")
                if strat == "waiter":
                    yield ("signal", "waiter")
        return g
    tr = run("dining_philosophers", [(f"P{i}", mk(i)) for i in range(n)], sems, sh, p["quantum"], input=p)
    total = sum(sh["meals"].values())
    tr.result["metrics"]["meals_eaten"] = total
    tr.result["explanation"] = ("Deadlock: every philosopher picked up the left fork and waits forever for the right one (circular wait)." if tr.result["deadlock"]
                                else f"No deadlock: all {total} meals were eaten" + {"ordered": " because forks are always taken in a global order, which breaks circular wait.",
                                                                                        "waiter": " because at most n-1 philosophers may sit at once, so one can always eat.",
                                                                                        "naive": " (a long time slice let each philosopher finish before the next started, so the circular wait never formed)."}[strat])
    return tr


RUNNERS = {"race_condition": _race, "critical_section": _critical, "binary_semaphore": _binary, "counting_semaphore": _counting,
           "producer_consumer": _pc, "readers_writers": _rw, "dining_philosophers": _dp}


def catalog():
    return [{"id": k, **v} for k, v in SCHEMAS.items()]


def run_scenario(name: str, params: dict):
    if name not in RUNNERS:
        raise ValidationError(f"Unknown scenario '{name}'. Supported: {', '.join(RUNNERS)}")
    out = {}
    for spec in SCHEMAS[name]["params"]:
        v = params.get(spec["name"], spec["default"])
        if spec["type"] == "int":
            if isinstance(v, bool) or not isinstance(v, int) or not spec["min"] <= v <= spec["max"]:
                raise ValidationError(f"{spec['label']} must be a whole number between {spec['min']} and {spec['max']}")
        elif spec["type"] == "bool":
            if not isinstance(v, bool):
                raise ValidationError(f"{spec['label']} must be true or false")
        elif v not in spec["options"]:
            raise ValidationError(f"{spec['label']} must be one of: {', '.join(spec['options'])}")
        out[spec["name"]] = v
    return RUNNERS[name](out)
