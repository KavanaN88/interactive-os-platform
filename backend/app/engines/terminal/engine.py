"""OS LAB Terminal: a strict-allowlist command interpreter over ONE simulated OS (process table, memory, disk, file system).
Nothing is ever executed on the host: no subprocess, eval, exec, SQL or real file access exists in this module.
Input is first restricted to a tiny character set (so shell metacharacters cannot even be typed), then matched
against a fixed table of commands; unknown commands are rejected."""
from __future__ import annotations

import re
import threading
from collections import OrderedDict

from app.engines.cpu import Process, simulate as cpu_simulate
from app.engines.cpu.models import ALGORITHMS as CPU_ALGOS
from app.engines.deadlock import engine as dl
from app.engines.disk import engine as disk
from app.engines.errors import ValidationError
from app.engines.fs import engine as fs
from app.engines.memory import engine as mem

CHARS = re.compile(r"^[A-Za-z0-9_./ \-]{1,200}$")
PID = re.compile(r"^[A-Za-z0-9_-]{1,16}$")
MAX_SESSIONS, MAX_PROCS, MAX_HISTORY, MAX_LINES = 200, 30, 200, 200
TOTAL_MEM, DISK_BLOCKS = 1024, 64
PRESETS = {
    "safe": ([3, 3, 2], [[0, 1, 0], [2, 0, 0], [3, 0, 2], [2, 1, 1], [0, 0, 2]], [[7, 5, 3], [3, 2, 2], [9, 0, 2], [2, 2, 2], [4, 3, 3]], [[0, 0, 0]] * 5),
    "unsafe": ([0], [[1], [1]], [[2], [2]], [[0], [0]]),
    "deadlock": ([0, 0], [[1, 0], [0, 1]], [[1, 1], [1, 1]], [[0, 1], [1, 0]]),
}


class Err(Exception):
    pass


class Session:
    def __init__(self):
        self.procs: OrderedDict[str, dict] = OrderedDict()
        self.mem_ops: list[dict] = []
        self.fs_method = "contiguous"
        self.fs_ops: list[dict] = []
        self.disk_queue: list[int] = []
        self.history: list[str] = []
        self.dl = "safe"


def _int(tok, name, lo, hi):
    if not re.fullmatch(r"\d{1,9}", tok or "") or not lo <= int(tok) <= hi:
        raise Err(f"{name} must be a whole number between {lo} and {hi}")
    return int(tok)


def _pid(tok):
    if not tok or not PID.match(tok):
        raise Err("A process id is 1-16 letters, digits, '_' or '-'")
    return tok


def _live(s, pid):
    p = s.procs.get(pid)
    if not p:
        raise Err(f"No such process: {pid}")
    return p


def _path(tok):
    if tok is None:
        raise Err("A path is required, e.g. /docs/a.txt")
    try:
        return fs.norm_path(tok)
    except ValidationError as e:
        raise Err(str(e))


# ---------------- commands: each returns a list of output lines ----------------
def c_os_info(s, a):
    return ["OS LAB Simulated OS 1.0 (educational simulation; nothing runs on your computer)",
            f"Memory     : {TOTAL_MEM} KB simulated RAM, variable partitions, first fit",
            f"Disk       : {DISK_BLOCKS} blocks, {s.fs_method} allocation",
            f"CPU        : schedulers available: {', '.join(CPU_ALGOS)}",
            f"Processes  : {len(s.procs)} in the table", "Type 'help' for the command list."]


def c_proc_list(s, a):
    if not s.procs:
        return ["No processes. Create one with: process create P1 5"]
    out = [f"{'PID':<10}{'STATE':<12}{'BURST':<7}{'PRIO':<6}{'MEM(KB)':<8}"]
    out += [f"{k:<10}{p['state']:<12}{p['burst']:<7}{p['priority']:<6}{p['mem']:<8}" for k, p in s.procs.items()]
    return out


def c_proc_create(s, a):
    if not 2 <= len(a) <= 4:
        raise Err("Usage: process create <pid> <burst> [priority] [mem_kb]")
    pid = _pid(a[0])
    burst = _int(a[1], "Burst", 1, 1000)
    prio = _int(a[2], "Priority", 0, 100) if len(a) > 2 else 1
    size = _int(a[3], "Memory", 1, TOTAL_MEM) if len(a) > 3 else 64
    if pid in s.procs and s.procs[pid]["state"] != "terminated":
        raise Err(f"Process {pid} already exists")
    if len([p for p in s.procs.values() if p["state"] != "terminated"]) >= MAX_PROCS:
        raise Err(f"Process table is full ({MAX_PROCS})")
    if pid in s.procs:                                   # reuse of a terminated pid: its memory was already freed
        del s.procs[pid]
    op = {"op": "alloc", "pid": pid, "size": size}
    tr = mem.simulate([TOTAL_MEM], s.mem_ops + [op], "first_fit", "variable")
    if tr.steps[-1].event != "alloc":
        raise Err(f"Cannot create {pid}: " + tr.steps[-1].explanation)
    s.mem_ops.append(op)
    s.procs[pid] = {"state": "ready", "burst": burst, "priority": prio, "mem": size}
    return [f"Created process {pid}: state=ready burst={burst} priority={prio}; {size} KB allocated at address {tr.steps[-1].state['chosen_start']}"]


def _free(s, pid):
    s.mem_ops.append({"op": "free", "pid": pid})


def c_proc_term(s, a):
    if len(a) != 1:
        raise Err("Usage: process terminate <pid>")
    pid = _pid(a[0])
    p = _live(s, pid)
    if p["state"] == "terminated":
        raise Err(f"Process {pid} is already terminated")
    p["state"] = "terminated"
    _free(s, pid)
    return [f"Process {pid} terminated; its {p['mem']} KB of memory was released"]


def c_proc_status(s, a):
    if len(a) != 1:
        raise Err("Usage: process status <pid>")
    pid = _pid(a[0])
    p = _live(s, pid)
    return [f"PID {pid}", f"  state     : {p['state']}", f"  burst     : {p['burst']} ticks", f"  priority  : {p['priority']} (lower number = higher priority)", f"  memory    : {p['mem']} KB"]


def c_cpu_status(s, a):
    cnt = {k: sum(1 for p in s.procs.values() if p["state"] == k) for k in ("ready", "terminated")}
    ready = [k for k, p in s.procs.items() if p["state"] == "ready"]
    work = sum(s.procs[k]["burst"] for k in ready)
    return [f"Ready processes     : {cnt['ready']}", f"Terminated          : {cnt['terminated']}", f"Pending CPU work    : {work} ticks",
            f"Next in ready queue : {ready[0] if ready else '-'}", "Run them with: scheduler run <algorithm> [quantum]"]


def c_sched_run(s, a):
    if not 1 <= len(a) <= 2 or a[0] not in CPU_ALGOS:
        raise Err(f"Usage: scheduler run <{'|'.join(CPU_ALGOS)}> [quantum]")
    q = _int(a[1], "Quantum", 1, 100) if len(a) > 1 else (2 if a[0] == "rr" else None)
    if a[0] == "rr" and q is None:
        q = 2
    ready = [k for k, p in s.procs.items() if p["state"] == "ready"]
    if not ready:
        raise Err("No ready processes. Create some first: process create P1 5")
    tr = cpu_simulate([Process(k, 0, s.procs[k]["burst"], s.procs[k]["priority"]) for k in ready], a[0], q)
    r, m = tr.result, tr.result["metrics"]
    out = [f"Scheduler: {r['algorithm_label']}" + (f" (quantum {q})" if a[0] == "rr" else ""), "Gantt: " + " ".join(f"[{g['pid'] or 'idle'} {g['start']}-{g['end']}]" for g in r["gantt"]),
           f"{'PID':<10}{'WAIT':<7}{'TURNAROUND':<12}{'RESPONSE':<9}"]
    out += [f"{x['pid']:<10}{x['waiting']:<7}{x['turnaround']:<12}{x['response']:<9}" for x in r["processes"]]
    out.append(f"avg wait {m['avg_waiting_time']} · avg turnaround {m['avg_turnaround_time']} · avg response {m['avg_response_time']} · context switches {m['context_switches']}")
    for k in ready:
        s.procs[k]["state"] = "terminated"
        _free(s, k)
    out.append(f"{len(ready)} process(es) ran to completion and released their memory.")
    return out


def c_mem_status(s, a):
    tr = mem.simulate([TOTAL_MEM], s.mem_ops or [{"op": "free", "pid": "none"}], "first_fit", "variable")
    st = tr.steps[-1].state
    segs = st["segments"]
    bar = "".join((seg["pid"][:1] if seg["pid"] else ".") * max(1, round(seg["size"] / TOTAL_MEM * 50)) for seg in segs)
    out = [f"Total {st['total_memory']} KB · allocated {st['allocated_memory']} KB · free {st['free_memory']} KB · utilization {st['utilization_pct']}%",
           f"Holes: {st['hole_count']} · largest hole {st['largest_hole']} KB · external fragmentation {st['external_fragmentation_pct']}%", "Map: [" + bar[:60] + "]"]
    out += [f"  {seg['start']:>5}-{seg['start'] + seg['size'] - 1:<5} {seg['pid'] or 'free':<10}{seg['size']} KB" for seg in segs]
    return out


def _fs_sim(s, extra=None):
    ops = s.fs_ops + ([extra] if extra else [])
    return fs.simulate(DISK_BLOCKS, s.fs_method, ops, 1) if ops else None


def c_disk_status(s, a):
    st = _fs_sim(s)
    used = st.steps[-1].state["used_blocks"] if st else 0
    head = s.disk_queue[-1] if s.disk_queue else 0
    out = [f"Disk: {DISK_BLOCKS} blocks, {used} used, {DISK_BLOCKS - used} free · head at cylinder {head}",
           f"Recent I/O requests ({len(s.disk_queue)}): {' '.join(map(str, s.disk_queue[-20:])) or 'none'}"]
    if len(s.disk_queue) >= 2:
        out.append("Head movement if this queue were scheduled (from cylinder 0):")
        for alg in ("fcfs", "sstf", "scan", "look"):
            t = disk.simulate(s.disk_queue[-50:], 0, DISK_BLOCKS - 1, "up", alg)
            out.append(f"  {disk.LABELS[alg]:<6} total {t.result['metrics']['total_head_movement']} cylinders")
    return out


def _fs_apply(s, op):
    tr = fs.simulate(DISK_BLOCKS, s.fs_method, s.fs_ops + [op], 1)
    last = tr.steps[-1]
    if last.event in ("error", "alloc_failed"):
        raise Err(last.explanation)
    if op["op"] != "read":
        s.fs_ops.append(op)
    reqs = last.state.get("disk_requests", [])
    s.disk_queue = (s.disk_queue + reqs)[-200:]
    return last, reqs


def c_fs_list(s, a):
    st = _fs_sim(s)
    if len(a) > 1:
        raise Err("Usage: filesystem list [path]")
    if not st:
        return ["/ (empty)"]
    path = _path(a[0]) if a else "/"

    def find(n):
        if n["path"] == path:
            return n
        for c in n.get("children", []):
            r = find(c)
            if r:
                return r
    node = find(st.result["tree"])
    if not node:
        raise Err(f"No such file or directory: {path}")
    if node["type"] == "file":
        return [f"{node['path']}  {node['size_kb']} KB  blocks {node['blocks']}"]
    out = [f"{path}:"]
    for c in node["children"]:
        out.append(f"  {'d' if c['type'] == 'dir' else '-'} {c['name']:<20}" + (f"{c['size_kb']} KB  blocks {c['blocks']}" if c["type"] == "file" else ""))
    return out if node["children"] else [f"{path}: (empty)"]


def c_fs_create(s, a):
    if len(a) != 2:
        raise Err("Usage: filesystem create <path> <blocks>")
    last, reqs = _fs_apply(s, {"op": "create", "path": _path(a[0]), "size": _int(a[1], "Blocks", 1, DISK_BLOCKS)})
    return [last.explanation, f"Disk requests generated: {' '.join(map(str, reqs))}"]


def c_fs_mkdir(s, a):
    if len(a) != 1:
        raise Err("Usage: filesystem mkdir <path>")
    return [_fs_apply(s, {"op": "mkdir", "path": _path(a[0])})[0].explanation]


def c_fs_delete(s, a):
    if len(a) != 1:
        raise Err("Usage: filesystem delete <path>")
    return [_fs_apply(s, {"op": "delete", "path": _path(a[0])})[0].explanation]


def c_fs_read(s, a):
    if len(a) != 1:
        raise Err("Usage: filesystem read <path>")
    last, reqs = _fs_apply(s, {"op": "read", "path": _path(a[0])})
    return [last.explanation, f"Blocks read, in order: {' '.join(map(str, reqs))}"]


def c_fs_format(s, a):
    if len(a) != 1 or a[0] not in fs.METHODS:
        raise Err(f"Usage: filesystem format <{'|'.join(fs.METHODS)}>  (erases the virtual disk)")
    s.fs_method, s.fs_ops, s.disk_queue = a[0], [], []
    return [f"Virtual disk formatted with {fs.LABELS[a[0]]}. All files removed."]


def c_dl_load(s, a):
    if len(a) != 1 or a[0] not in PRESETS:
        raise Err(f"Usage: deadlock load <{'|'.join(PRESETS)}>")
    s.dl = a[0]
    return [f"Loaded the '{a[0]}' resource scenario. Run: deadlock check"]


def c_dl_check(s, a):
    av, al, mx, rq = PRESETS[s.dl]
    sf = dl.safety(av, al, mx).result
    dt = dl.detect(av, al, rq).result
    out = [f"Scenario: {s.dl}  ({len(al)} processes, {len(av)} resource type(s))",
           "Banker's safety check: " + (f"SAFE, sequence <{', '.join(sf['sequence'])}>" if sf["safe"] else f"UNSAFE (cannot finish: {', '.join(sf['unfinished'])})"),
           "Deadlock detection  : " + (f"DEADLOCK among {', '.join(dt['deadlocked'])}" if dt["has_deadlock"] else "no deadlock")]
    if not sf["safe"] and not dt["has_deadlock"]:
        out.append("Note: an unsafe state is a warning; it does not mean deadlock has happened yet.")
    return out


def c_history(s, a):
    return [f"{i + 1:>4}  {h}" for i, h in enumerate(s.history)] or ["(no history yet)"]


COMMANDS = {
    ("os-info",): (c_os_info, "os-info", "Show information about the simulated OS"),
    ("process", "list"): (c_proc_list, "process list", "List all processes"),
    ("process", "create"): (c_proc_create, "process create <pid> <burst> [priority] [mem_kb]", "Create a process (allocates simulated memory)"),
    ("process", "terminate"): (c_proc_term, "process terminate <pid>", "Terminate a process and free its memory"),
    ("process", "status"): (c_proc_status, "process status <pid>", "Show one process"),
    ("cpu", "status"): (c_cpu_status, "cpu status", "Show CPU / ready-queue state"),
    ("scheduler", "run"): (c_sched_run, "scheduler run <algorithm> [quantum]", "Run all ready processes with a scheduling algorithm"),
    ("memory", "status"): (c_mem_status, "memory status", "Show the memory map and fragmentation"),
    ("disk", "status"): (c_disk_status, "disk status", "Show disk usage, head position and scheduling cost"),
    ("deadlock", "check"): (c_dl_check, "deadlock check", "Run the Banker's safety check and deadlock detection"),
    ("deadlock", "load"): (c_dl_load, "deadlock load <safe|unsafe|deadlock>", "Load a resource scenario"),
    ("filesystem", "list"): (c_fs_list, "filesystem list [path]", "List a directory of the virtual disk"),
    ("filesystem", "create"): (c_fs_create, "filesystem create <path> <blocks>", "Create a file of N blocks"),
    ("filesystem", "mkdir"): (c_fs_mkdir, "filesystem mkdir <path>", "Create a directory"),
    ("filesystem", "delete"): (c_fs_delete, "filesystem delete <path>", "Delete a file or empty directory"),
    ("filesystem", "read"): (c_fs_read, "filesystem read <path>", "Read a file (shows the blocks touched)"),
    ("filesystem", "format"): (c_fs_format, "filesystem format <contiguous|linked|indexed>", "Re-format the virtual disk"),
    ("history",): (c_history, "history", "Show previous commands"),
}


def c_help(s, a):
    if a:
        hit = [v for k, v in COMMANDS.items() if k[0] == a[0] and (len(a) == 1 or k[1:2] == tuple(a[1:2]))]
        if not hit:
            raise Err(f"No help for '{' '.join(a)}'. Type 'help' for the list.")
        return [f"{u}\n    {d}" for _, u, d in hit]
    return ["Commands (everything runs inside the simulation):"] + [f"  {u:<52}{d}" for _, u, d in COMMANDS.values()] + ["  help [command]                                      Show this help", "  clear                                               Clear the screen"]


_SESSIONS: "OrderedDict[str, Session]" = OrderedDict()
_LOCK = threading.Lock()
_SID = re.compile(r"^[A-Za-z0-9-]{8,64}$")


def execute(session_id: str, line: str) -> dict:
    if not isinstance(session_id, str) or not _SID.match(session_id):
        raise ValidationError("Invalid session id")
    if not isinstance(line, str):
        raise ValidationError("command must be text")
    line = line.strip()
    with _LOCK:
        s = _SESSIONS.get(session_id)
        if s is None:
            s = _SESSIONS[session_id] = Session()
            while len(_SESSIONS) > MAX_SESSIONS:
                _SESSIONS.popitem(last=False)
        _SESSIONS.move_to_end(session_id)
        if not line:
            return {"output": [], "ok": True, "clear": False}
        if not CHARS.match(line):
            return {"output": ["Rejected: only letters, digits, spaces and _ . / - are allowed. Shell, SQL and script syntax is never executed here."], "ok": False, "clear": False}
        s.history = (s.history + [line])[-MAX_HISTORY:]
        tok = line.split()
        if tok[0] == "clear" and len(tok) == 1:
            return {"output": [], "ok": True, "clear": True}
        try:
            if tok[0] == "help":
                out = c_help(s, tok[1:])
            else:
                key = next((k for k in COMMANDS if tuple(tok[:len(k)]) == k), None)
                if key is None:
                    raise Err(f"Command not found: {tok[0]}. Type 'help' to see the supported commands.")
                out = COMMANDS[key][0](s, tok[len(key):])
        except Err as e:
            return {"output": [str(e)], "ok": False, "clear": False}
        out = [ln for chunk in out for ln in chunk.split("\n")][:MAX_LINES]
        return {"output": out, "ok": True, "clear": False}


def reset_sessions():
    with _LOCK:
        _SESSIONS.clear()
