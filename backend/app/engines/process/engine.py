"""Process lifecycle simulator: PCBs, five states, round-robin dispatch, I/O waits, context switches, process tree.
A program is a list of bursts that alternates CPU, I/O, CPU, ... and must start and end with CPU, e.g. [3, 2, 4].
Order inside a tick: arrivals, then I/O completions (input order), then a preempted process re-queues."""
from __future__ import annotations

import re
from collections import deque

from app.engines.errors import ValidationError
from app.engines.trace import SimulationTrace

STATES = ["new", "ready", "running", "waiting", "terminated"]
MAX_PROCS, MAX_TICKS = 20, 5000
_PID = re.compile(r"^[A-Za-z0-9_-]{1,16}$")


def _int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def validate(procs, quantum):
    if not _int(quantum) or not 1 <= quantum <= 100:
        raise ValidationError("Time quantum must be a whole number between 1 and 100")
    if not isinstance(procs, list) or not 1 <= len(procs) <= MAX_PROCS:
        raise ValidationError(f"Provide 1..{MAX_PROCS} processes")
    seen = {}
    for p in procs:
        pid = p.get("pid")
        if not isinstance(pid, str) or not _PID.match(pid):
            raise ValidationError("Process ids must be 1-16 letters, digits, '_' or '-'")
        if pid in seen:
            raise ValidationError(f"Duplicate process id '{pid}'")
        if not _int(p.get("arrival")) or p["arrival"] < 0:
            raise ValidationError(f"{pid}: arrival must be a whole number >= 0")
        b = p.get("bursts")
        if not isinstance(b, list) or not b or len(b) % 2 == 0 or len(b) > 9 or any(not _int(x) or not 1 <= x <= 1000 for x in b):
            raise ValidationError(f"{pid}: bursts must be 1, 3, 5, 7 or 9 whole numbers (CPU, I/O, CPU, ...), each 1-1000")
        if not _int(p.get("priority", 0)):
            raise ValidationError(f"{pid}: priority must be a whole number")
        mem = p.get("memory", 64)
        if not _int(mem) or not 1 <= mem <= 1_000_000:
            raise ValidationError(f"{pid}: memory must be a whole number of KB")
        par = p.get("parent")
        if par is not None:
            if par not in seen:
                raise ValidationError(f"{pid}: parent '{par}' must be listed before its child")
            if p["arrival"] < seen[par]["arrival"]:
                raise ValidationError(f"{pid}: a child cannot be created before its parent ({par})")
        seen[pid] = p
    if max(p["arrival"] for p in procs) + sum(sum(p["bursts"]) for p in procs) > MAX_TICKS:
        raise ValidationError(f"Workload too large (more than {MAX_TICKS} simulated ticks)")


def _tree(procs):
    kids = {p["pid"]: [] for p in procs}
    roots = []
    for p in procs:
        (kids[p["parent"]] if p.get("parent") else roots).append(p["pid"])
    build = lambda pid: {"pid": pid, "children": [build(c) for c in kids[pid]]}
    return [build(r) for r in roots]


def simulate(procs: list[dict], quantum: int = 2) -> SimulationTrace:
    validate(procs, quantum)
    order = [p["pid"] for p in procs]
    R = {p["pid"]: {"p": p, "state": None, "idx": 0, "rem": p["bursts"][0], "acc": 0, "io": 0, "first": None, "done": None,
                    "time": {s: 0 for s in STATES}} for p in procs}
    trace = SimulationTrace("process_management", "lifecycle", {"processes": procs, "quantum": quantum})
    tl = {pid: [] for pid in order}
    trans: dict[str, int] = {}
    ready, running, last_run, slice_used, ctx, t = deque(), None, None, 0, 0, 0
    done = 0

    def regs(pid):
        r = R[pid]
        return {"PC": 0x1000 + 4 * r["acc"], "SP": 0x7FFF0000 - 0x1000 * order.index(pid), "ACC": r["acc"]}

    def snap():
        procs_now = {}
        for pid in order:
            r = R[pid]
            if r["state"] is None:
                continue
            procs_now[pid] = {"state": r["state"], "priority": r["p"].get("priority", 0), "memory_kb": r["p"].get("memory", 64),
                              "parent": r["p"].get("parent"), "regs": regs(pid), "remaining_in_burst": r["rem"] if r["state"] != "terminated" else 0,
                              "io_remaining": r["io"] if r["state"] == "waiting" else 0}
        return {"processes": procs_now, "running": running, "ready": list(ready),
                "waiting": [p for p in order if R[p]["state"] == "waiting"]}

    def move(pid, new, why, event, action, extra=None):
        nonlocal done
        old = R[pid]["state"]
        if tl[pid]:
            tl[pid][-1]["end"] = t
        if new != "terminated":
            tl[pid].append({"state": new, "start": t, "end": t})
        R[pid]["state"] = new
        if old:
            trans[f"{old}->{new}"] = trans.get(f"{old}->{new}", 0) + 1
        if new == "terminated":
            R[pid]["done"] = t
            done += 1
        s = snap()
        s["transition"] = [old, new]
        s["pid"] = pid
        if extra:
            s.update(extra)
        trace.add(t, event, action, why, s)

    def arrivals(now):
        for pid in order:
            if R[pid]["p"]["arrival"] == now and R[pid]["state"] is None:
                par = R[pid]["p"].get("parent")
                move(pid, "new", f"{pid} is created" + (f" by its parent {par} (fork): a new PCB is built" if par else ": the OS builds its PCB and assigns a process id"),
                     "create", f"{pid} created")
                ready.append(pid)
                move(pid, "ready", f"{pid} is admitted to the ready queue", "admit", f"{pid} admitted")

    def io_done(now):
        for pid in order:
            if R[pid]["state"] == "waiting" and R[pid]["io"] <= 0:
                ready.append(pid)
                move(pid, "ready", f"{pid} finished its I/O and returns to the ready queue", "io_complete", f"{pid} I/O done")

    arrivals(0)
    io_done(0)
    while done < len(order):
        if t > MAX_TICKS:
            raise ValidationError("Simulation exceeded the tick limit")
        if running is None and ready:
            pid = ready.popleft()
            switch = None
            if last_run is not None and last_run != pid:
                ctx += 1
                switch = {"saved": {"pid": last_run, "regs": regs(last_run)}, "restored": {"pid": pid, "regs": regs(pid)}}
            if R[pid]["first"] is None:
                R[pid]["first"] = t
            running, slice_used = pid, 0
            why = f"The scheduler picks {pid} from the head of the ready queue"
            if switch:
                why += f". Context switch: {last_run}'s registers are already saved in its PCB; {pid}'s saved registers (PC={switch['restored']['regs']['PC']}) are restored"
            move(pid, "running", why, "dispatch", f"{pid} dispatched", {"context_switch": switch})
        waiting_before = [p for p in order if R[p]["state"] == "waiting"]
        if running:
            R[running]["rem"] -= 1
            R[running]["acc"] += 1
            slice_used += 1
            last_run = running
        for p in waiting_before:
            R[p]["io"] -= 1
        t += 1
        arrivals(t)
        io_done(t)
        if running:
            pid, r = running, R[running]
            if r["rem"] == 0:
                running = None
                if r["idx"] == len(r["p"]["bursts"]) - 1:
                    move(pid, "terminated", f"{pid} finished its last CPU burst: its resources are released and the PCB is removed (context saved: PC={regs(pid)['PC']})", "terminate", f"{pid} terminated")
                else:
                    r["io"] = r["p"]["bursts"][r["idx"] + 1]
                    r["idx"] += 2
                    r["rem"] = r["p"]["bursts"][r["idx"]]
                    move(pid, "waiting", f"{pid} requests I/O for {r['io']} ticks: its context is saved and it blocks (PC={regs(pid)['PC']})", "io_request", f"{pid} waits for I/O")
            elif slice_used >= quantum:
                running = None
                ready.append(pid)
                move(pid, "ready", f"{pid} used its time quantum ({quantum}); the timer interrupt saves its context (PC={regs(pid)['PC']}) and it goes back to the ready queue", "preempt", f"{pid} preempted")

    for pid in order:
        if tl[pid]:
            tl[pid][-1]["end"] = tl[pid][-1]["end"] if R[pid]["state"] == "terminated" else t
    per = []
    for pid in order:
        r = R[pid]
        segs = tl[pid]
        dur = lambda s: sum(x["end"] - x["start"] for x in segs if x["state"] == s)
        per.append({"pid": pid, "arrival": r["p"]["arrival"], "completion": r["done"], "turnaround": r["done"] - r["p"]["arrival"],
                    "response": r["first"] - r["p"]["arrival"], "cpu_time": dur("running"), "ready_time": dur("ready"), "io_time": dur("waiting")})
    busy = sum(x["cpu_time"] for x in per)
    trace.result = {
        "timeline": tl, "tree": _tree(procs), "processes": per, "transitions": trans,
        "metrics": {"context_switches": ctx, "makespan": t, "cpu_utilization": round(100 * busy / t, 2),
                    "avg_turnaround": round(sum(x["turnaround"] for x in per) / len(per), 4),
                    "avg_response": round(sum(x["response"] for x in per) / len(per), 4)},
    }
    return trace


# ---------------- Inter-process communication ----------------
IPC = {"pipe": "Pipe: a one-way byte channel with a fixed capacity; writers block when it is full, readers block when it is empty.",
       "message_queue": "Message queue: the kernel stores whole messages in order; senders block when full, receivers when empty.",
       "shared_memory": "Shared memory: processes read and write the same region directly; fast, but they must synchronise themselves."}


def ipc(mechanism: str, ops: list[dict], capacity: int = 3) -> SimulationTrace:
    if mechanism not in IPC:
        raise ValidationError(f"Unknown mechanism '{mechanism}'. Supported: {', '.join(IPC)}")
    if not _int(capacity) or not 1 <= capacity <= 16:
        raise ValidationError("Capacity must be between 1 and 16")
    if not isinstance(ops, list) or not 1 <= len(ops) <= 100:
        raise ValidationError("Provide 1..100 operations")
    valid = {"send", "recv"} if mechanism != "shared_memory" else {"write", "read"}
    for o in ops:
        if not isinstance(o.get("by"), str) or not _PID.match(o["by"]):
            raise ValidationError("Each operation needs a process name in 'by'")
        if o.get("op") not in valid:
            raise ValidationError(f"For {mechanism} use operations: {', '.join(sorted(valid))}")
        if o["op"] in ("send", "write") and (not isinstance(o.get("data"), (str, int)) or len(str(o["data"])) > 32):
            raise ValidationError("data must be short text or a number (max 32 characters)")
        if mechanism == "shared_memory" and (not isinstance(o.get("key"), str) or not _PID.match(o["key"])):
            raise ValidationError("Shared-memory operations need a short 'key' (the memory slot name)")
    trace = SimulationTrace("process_management", mechanism, {"ops": ops, "capacity": capacity})
    buf, blocked, mem, last_writer = [], [], {}, {}
    violations = 0
    snap = lambda: {"buffer": list(buf), "capacity": capacity, "blocked": [f"{b['by']}:{b['op']}" for b in blocked], "memory": dict(mem)}

    def attempt(o):
        if mechanism == "shared_memory":
            if o["op"] == "write":
                prev = last_writer.get(o["key"])
                msg = f"{o['by']} writes '{o['data']}' into slot {o['key']}"
                ev = "write"
                if prev and prev != o["by"] and o["key"] in mem:
                    msg += f", overwriting {prev}'s value '{mem[o['key']]}' (no synchronisation: a lost update)"
                    ev = "violation"
                mem[o["key"]] = o["data"]
                last_writer[o["key"]] = o["by"]
                return True, ev, msg
            if o["key"] not in mem:
                return True, "violation", f"{o['by']} reads slot {o['key']} before anything was written (stale or empty data)"
            return True, "read", f"{o['by']} reads '{mem[o['key']]}' from slot {o['key']} directly, with no kernel copy"
        if o["op"] == "send":
            if len(buf) >= capacity:
                return False, "blocked", f"{o['by']} cannot send: the {mechanism.replace('_', ' ')} is full ({capacity}/{capacity}), so it blocks"
            buf.append(o["data"])
            return True, "send", f"{o['by']} sends '{o['data']}' ({len(buf)}/{capacity} used)"
        if not buf:
            return False, "blocked", f"{o['by']} cannot receive: nothing is available, so it blocks"
        v = buf.pop(0)
        return True, "recv", f"{o['by']} receives '{v}' ({len(buf)}/{capacity} used)"

    trace.add(0, "init", "Start", IPC[mechanism], snap())
    for i, o in enumerate(ops, start=1):
        ok, ev, msg = attempt(o)
        if not ok:
            blocked.append(o)
            trace.add(i, "blocked", f"{o['by']} blocks", msg, snap())
            continue
        violations += ev == "violation"
        trace.add(i, ev, f"{o['by']} {o['op']}", msg, snap())
        progressed = True
        while progressed and blocked:
            progressed = False
            for b in list(blocked):
                ok, ev2, msg2 = attempt(b)
                if ok:
                    blocked.remove(b)
                    trace.add(i, "unblocked", f"{b['by']} resumes", "Unblocked: " + msg2, snap())
                    progressed = True
                    break
    trace.result = {"description": IPC[mechanism], "still_blocked": [f"{b['by']}:{b['op']}" for b in blocked],
                    "metrics": {"operations": len(ops), "blocked_at_end": len(blocked), "violations": violations}}
    return trace


def threads_demo(threads: int, work: int) -> SimulationTrace:
    if not _int(threads) or not 1 <= threads <= 8 or not _int(work) or not 1 <= work <= 20:
        raise ValidationError("Use 1-8 threads and 1-20 work units")
    trace = SimulationTrace("process_management", "threads", {"threads": threads, "work": work})
    shared = {"code": "same program text", "heap_counter": 0}
    stacks = {f"T{i + 1}": {"local_sum": 0, "SP": 0x7000 - 0x400 * i, "PC": 0x1000} for i in range(threads)}
    done = {k: 0 for k in stacks}
    t = 0
    while any(d < work for d in done.values()):
        for k in stacks:
            if done[k] < work:
                done[k] += 1
                stacks[k]["local_sum"] += done[k]
                stacks[k]["PC"] += 4
                shared["heap_counter"] += 1
                t += 1
                trace.add(t, "run", f"{k} runs", f"{k} adds {done[k]} to ITS OWN stack variable (local_sum={stacks[k]['local_sum']}) and increments the SHARED heap counter to {shared['heap_counter']}",
                          {"shared": dict(shared), "stacks": {a: dict(b) for a, b in stacks.items()}, "running": k})
    trace.result = {"shared": shared, "stacks": stacks,
                    "explanation": "Threads of one process share code, data and heap, but each has its own stack and registers (PC, SP)."}
    return trace
