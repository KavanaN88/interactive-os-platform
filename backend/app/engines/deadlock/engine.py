"""Deadlock: Banker's safety + request check, matrix-based detection, recovery by termination, resource allocation graph.
Processes are P0..Pn-1 and resources R0..Rm-1. Scans always restart from P0, so the safe sequence is deterministic."""
from __future__ import annotations

from app.engines.errors import ValidationError
from app.engines.trace import SimulationTrace

MAX_P, MAX_R = 20, 10


def _int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _matrix(name, m, n, cols):
    if not isinstance(m, list) or len(m) != n or any(not isinstance(r, list) or len(r) != cols for r in m):
        raise ValidationError(f"{name} must be a {n}x{cols} matrix")
    if any(not _int(x) or x < 0 or x > 100_000 for r in m for x in r):
        raise ValidationError(f"{name} must contain whole numbers >= 0")


def _vec(name, v, cols):
    if not isinstance(v, list) or len(v) != cols or any(not _int(x) or x < 0 or x > 100_000 for x in v):
        raise ValidationError(f"{name} must be a list of {cols} whole numbers >= 0")


def _dims(available, allocation):
    m = len(available) if isinstance(available, list) else 0
    n = len(allocation) if isinstance(allocation, list) else 0
    if not 1 <= n <= MAX_P or not 1 <= m <= MAX_R:
        raise ValidationError(f"Use 1..{MAX_P} processes and 1..{MAX_R} resource types")
    return n, m


def need_matrix(maximum, allocation):
    return [[mx - al for mx, al in zip(rm, ra)] for rm, ra in zip(maximum, allocation)]


def _check_banker(available, allocation, maximum):
    n, m = _dims(available, allocation)
    _vec("Available", available, m)
    _matrix("Allocation", allocation, n, m)
    _matrix("Maximum", maximum, n, m)
    for i in range(n):
        for j in range(m):
            if allocation[i][j] > maximum[i][j]:
                raise ValidationError(f"P{i}: allocation of R{j} ({allocation[i][j]}) exceeds its maximum ({maximum[i][j]})")
    return n, m


def _le(a, b):
    return all(x <= y for x, y in zip(a, b))


def safety(available, allocation, maximum) -> SimulationTrace:
    n, m = _check_banker(available, allocation, maximum)
    need = need_matrix(maximum, allocation)
    work, finished, seq = list(available), [False] * n, []
    trace = SimulationTrace("deadlock", "banker_safety", {"available": available, "allocation": allocation, "maximum": maximum})
    snap = lambda: {"work": list(work), "finished": [f"P{i}" for i in range(n) if finished[i]], "sequence": list(seq)}
    trace.add(0, "init", "Initialise", f"Need = Maximum − Allocation. Work starts as Available {work}", snap())
    while True:
        skipped = []
        pick = None
        for i in range(n):
            if finished[i]:
                continue
            if _le(need[i], work):
                pick = i
                break
            skipped.append(f"P{i} (need {need[i]} > work {work})")
        if pick is None:
            break
        work = [w + a for w, a in zip(work, allocation[pick])]
        finished[pick] = True
        seq.append(f"P{pick}")
        why = f"P{pick}: need {need[pick]} ≤ work, so it can finish and release {allocation[pick]}; work becomes {work}"
        if skipped:
            why = "Skipped " + "; ".join(skipped) + ". " + why
        trace.add(len(seq), "finish", f"P{pick} finishes", why, snap())
    safe = all(finished)
    stuck = [f"P{i}" for i in range(n) if not finished[i]]
    trace.add(len(seq) + 1, "safe" if safe else "unsafe", "Result",
              f"Safe state. Safe sequence: <{', '.join(seq)}>" if safe else
              f"Unsafe state: no remaining process ({', '.join(stuck)}) can finish with work {work}. Unsafe does not mean deadlock has already occurred.",
              snap())
    trace.result = {"safe": safe, "sequence": seq, "unfinished": stuck, "need": need, "final_work": work}
    return trace


def request(available, allocation, maximum, pid, req) -> dict:
    n, m = _check_banker(available, allocation, maximum)
    if not _int(pid) or not 0 <= pid < n:
        raise ValidationError(f"Process index must be between 0 and {n - 1}")
    _vec("Request", req, m)
    need = need_matrix(maximum, allocation)
    if not _le(req, need[pid]):
        return {"granted": False, "reason": f"Denied: P{pid} requests more than its remaining need {need[pid]} (it exceeded its declared maximum)."}
    if not _le(req, available):
        return {"granted": False, "reason": f"P{pid} must wait: requested {req} is more than the available {available}."}
    new_av = [a - r for a, r in zip(available, req)]
    new_al = [row[:] for row in allocation]
    new_al[pid] = [a + r for a, r in zip(new_al[pid], req)]
    tr = safety(new_av, new_al, maximum)
    if tr.result["safe"]:
        return {"granted": True, "reason": f"Granted: after the tentative allocation the state is safe, sequence <{', '.join(tr.result['sequence'])}>.",
                "available": new_av, "allocation": new_al, "safety": tr.to_dict()}
    return {"granted": False, "reason": "Denied: granting the request would leave the system in an unsafe state, so P"
            f"{pid} must wait.", "safety": tr.to_dict()}


def _check_detect(available, allocation, req_matrix):
    n, m = _dims(available, allocation)
    _vec("Available", available, m)
    _matrix("Allocation", allocation, n, m)
    _matrix("Request", req_matrix, n, m)
    return n, m


def detect(available, allocation, requests) -> SimulationTrace:
    n, m = _check_detect(available, allocation, requests)
    work = list(available)
    finished = [all(x == 0 for x in allocation[i]) for i in range(n)]
    seq = []
    trace = SimulationTrace("deadlock", "detection", {"available": available, "allocation": allocation, "request": requests})
    snap = lambda: {"work": list(work), "finished": [f"P{i}" for i in range(n) if finished[i]], "sequence": list(seq)}
    trace.add(0, "init", "Initialise", f"Work = Available {work}. Processes holding nothing are marked finished.", snap())
    while True:
        pick = next((i for i in range(n) if not finished[i] and _le(requests[i], work)), None)
        if pick is None:
            break
        work = [w + a for w, a in zip(work, allocation[pick])]
        finished[pick] = True
        seq.append(f"P{pick}")
        trace.add(len(seq), "finish", f"P{pick} can finish", f"P{pick}: request {requests[pick]} ≤ work, so it completes and releases {allocation[pick]}; work becomes {work}", snap())
    dead = [f"P{i}" for i in range(n) if not finished[i]]
    trace.add(len(seq) + 1, "deadlock" if dead else "safe", "Result",
              f"Deadlock: {', '.join(dead)} are waiting on each other and can never proceed." if dead else "No deadlock: every process can complete.", snap())
    trace.result = {"deadlocked": dead, "has_deadlock": bool(dead), "sequence": seq}
    return trace


def recover(available, allocation, requests) -> SimulationTrace:
    """Recovery by process termination: repeatedly abort the deadlocked process holding the most resources."""
    n, m = _check_detect(available, allocation, requests)
    av, al, rq = list(available), [r[:] for r in allocation], [r[:] for r in requests]
    trace = SimulationTrace("deadlock", "recovery", {"available": available, "allocation": allocation, "request": requests})
    terminated = []
    for rnd in range(n + 1):
        d = detect(av, al, rq).result
        if not d["has_deadlock"]:
            trace.add(rnd, "recovered", "Recovered", "No deadlock remains." if terminated else "No deadlock was present.",
                      {"available": list(av), "terminated": list(terminated), "allocation": [r[:] for r in al]})
            break
        victim = max((int(p[1:]) for p in d["deadlocked"]), key=lambda i: (sum(al[i]), -i))
        released = al[victim]
        av = [a + r for a, r in zip(av, released)]
        al[victim], rq[victim] = [0] * m, [0] * m
        terminated.append(f"P{victim}")
        trace.add(rnd, "terminate", f"Terminate P{victim}",
                  f"Deadlocked: {', '.join(d['deadlocked'])}. P{victim} holds the most resources ({sum(released)} units) so it is terminated; available becomes {av}",
                  {"available": list(av), "terminated": list(terminated), "allocation": [r[:] for r in al]})
    trace.result = {"terminated": terminated, "final_available": av, "final_allocation": al}
    return trace


def rag(available, allocation, requests) -> dict:
    n, m = _check_detect(available, allocation, requests)
    inst = [available[j] + sum(allocation[i][j] for i in range(n)) for j in range(m)]
    nodes = [{"id": f"P{i}", "type": "process"} for i in range(n)] + [{"id": f"R{j}", "type": "resource", "instances": inst[j]} for j in range(m)]
    edges = ([{"from": f"R{j}", "to": f"P{i}", "kind": "allocation", "count": allocation[i][j]} for i in range(n) for j in range(m) if allocation[i][j]]
             + [{"from": f"P{i}", "to": f"R{j}", "kind": "request", "count": requests[i][j]} for i in range(n) for j in range(m) if requests[i][j]])
    adj: dict[str, list[str]] = {}
    for e in edges:
        adj.setdefault(e["from"], []).append(e["to"])
    cycle, state = [], {}

    def dfs(u, stack):
        state[u] = 1
        stack.append(u)
        for v in adj.get(u, []):
            if state.get(v) == 1:
                cycle.extend(stack[stack.index(v):])
                return True
            if state.get(v) is None and dfs(v, stack):
                return True
        stack.pop()
        state[u] = 2
        return False

    for node in [x["id"] for x in nodes]:
        if state.get(node) is None and dfs(node, []):
            break
    single = all(inst[int(c[1:])] == 1 for c in cycle if c.startswith("R")) if cycle else False
    note = ("No cycle in the graph, so there is no deadlock." if not cycle else
            "A cycle exists and every resource in it has a single instance, so these processes are deadlocked." if single else
            "A cycle exists, but some resources have several instances, so a cycle is necessary but not sufficient for deadlock; run detection to be sure.")
    return {"nodes": nodes, "edges": edges, "cycle": cycle, "cycle_is_deadlock": bool(cycle) and single, "explanation": note}
