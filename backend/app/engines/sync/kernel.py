"""Deterministic concurrency kernel. A thread is a generator; every `yield` is one scheduler tick.
Effects of an action run when the thread is resumed, then it yields a description of what it did, so interleavings
at instruction granularity are real (that is what makes race conditions reproducible).
Yield forms: ("do", text[, "violation"]) | ("wait", sem) | ("signal", sem).
Semaphores hand ownership directly to the first waiter on signal (FIFO), so wake-ups are deterministic."""
from __future__ import annotations

import copy
from collections import deque

from app.engines.trace import SimulationTrace


class Sem:
    def __init__(self, name, value):
        self.name, self.value, self.queue, self.holders = name, value, deque(), []


def run(algorithm, threads, sems, shared, quantum=1, max_ticks=3000, input=None) -> SimulationTrace:
    trace = SimulationTrace("synchronization", algorithm, input or {})
    S = {n: Sem(n, v) for n, v in sems.items()}
    order = [n for n, _ in threads]
    T = {n: {"gen": f(), "state": "ready", "on": None} for n, f in threads}
    ready = deque(order)
    tick, violations, deadlock = 0, 0, False

    def snap(running=None):
        return {"shared": copy.deepcopy(shared),
                "sems": {n: {"value": s.value, "queue": list(s.queue), "holders": list(s.holders)} for n, s in S.items()},
                "threads": {n: T[n]["state"] for n in order}, "running": running}

    trace.add(0, "init", "Start", "All threads are ready; the scheduler is round-robin with a quantum of "
              f"{quantum} operation(s)", snap())
    while ready:
        if tick >= max_ticks:
            trace.add(tick, "timeout", "Stopped", f"Stopped after {max_ticks} ticks (possible livelock)", snap())
            break
        n = ready.popleft()
        used = 0
        while used < quantum and T[n]["state"] == "ready":
            try:
                op = next(T[n]["gen"])
            except StopIteration:
                T[n]["state"] = "done"
                tick += 1
                trace.add(tick, "done", f"{n} finishes", f"{n} has completed all of its work", snap(n))
                break
            used += 1
            tick += 1
            kind = op[0]
            if kind == "do":
                bad = len(op) > 2 and op[2] == "violation"
                violations += bad
                trace.add(tick, "violation" if bad else "do", n, op[1], snap(n))
            elif kind == "wait":
                s = S[op[1]]
                if s.value > 0:
                    s.value -= 1
                    s.holders.append(n)
                    trace.add(tick, "wait", n, f"{n} executes wait({s.name}): value becomes {s.value}; {n} continues", snap(n))
                else:
                    s.queue.append(n)
                    T[n].update(state="blocked", on=s.name)
                    trace.add(tick, "blocked", n, f"{n} executes wait({s.name}) but the value is 0, so {n} BLOCKS in the queue of {s.name}", snap(n))
            else:  # signal
                s = S[op[1]]
                if n in s.holders:
                    s.holders.remove(n)
                if s.queue:
                    w = s.queue.popleft()
                    s.holders.append(w)
                    T[w].update(state="ready", on=None)
                    ready.append(w)
                    trace.add(tick, "signal", n, f"{n} executes signal({s.name}); {w} is woken up and now owns it", snap(n))
                else:
                    s.value += 1
                    trace.add(tick, "signal", n, f"{n} executes signal({s.name}): value becomes {s.value}", snap(n))
        if T[n]["state"] == "ready":
            ready.append(n)
    unfinished = [n for n in order if T[n]["state"] != "done"]
    if unfinished and not ready and any(T[n]["state"] == "blocked" for n in unfinished) and tick < max_ticks:
        deadlock = True
        waits = {n: T[n]["on"] for n in unfinished if T[n]["state"] == "blocked"}
        trace.add(tick + 1, "deadlock", "Deadlock",
                  "DEADLOCK: no thread can run. " + "; ".join(f"{a} waits for {b}" + (f" (held by {', '.join(S[b].holders)})" if S[b].holders else "") for a, b in waits.items()), snap())
    trace.result = {"shared": copy.deepcopy(shared), "ticks": tick, "deadlock": deadlock, "violations": violations,
                    "unfinished": unfinished, "metrics": {"ticks": tick, "violations": violations, "deadlock": int(deadlock)}}
    return trace
