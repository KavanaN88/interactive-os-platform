"""Quiz engine. Multiple-choice questions are static; numerical questions are GENERATED from the simulators with a
seed that is embedded in the question id, so grading recomputes the answer from the engine (stateless, no stored answers)
and the correct answer is never sent before submission."""
from __future__ import annotations

import random
import re

from app.engines.cpu import Process, simulate as cpu_sim
from app.engines.deadlock import engine as dl
from app.engines.disk import engine as disk
from app.engines.errors import ValidationError
from app.engines.fs import engine as fs
from app.engines.learn.content import MODULES
from app.engines.memory import engine as mem
from app.engines.paging import engine as paging
from app.engines.process import engine as proc
from app.engines.sync.scenarios import run_scenario

LEVELS = ["beginner", "intermediate", "advanced"]
MOD_IDS = [m for m, _ in MODULES]

# (module, level, prompt, options, correct_index, explanation)
MCQ = [
    ("cpu", "beginner", "Waiting time of a process is…", ["completion − arrival", "turnaround − burst", "first run − arrival", "burst − arrival"], 1, "Waiting = turnaround − burst. Response time is first run − arrival."),
    ("cpu", "intermediate", "Which algorithm gives the minimum average waiting time when all burst times are known?", ["FCFS", "Round Robin", "Shortest Job First", "Priority"], 2, "SJF is provably optimal for average waiting time (non-preemptive, known bursts)."),
    ("cpu", "advanced", "In a multilevel feedback queue, a process that uses its whole quantum is…", ["promoted", "demoted to a lower queue", "terminated", "moved to the I/O queue"], 1, "Using the full quantum suggests a CPU-bound job, so it is demoted."),
    ("process", "beginner", "Which state does a process enter when it requests I/O?", ["Ready", "New", "Waiting", "Terminated"], 2, "Running → Waiting on an I/O request."),
    ("process", "intermediate", "What is saved in the PCB during a context switch?", ["Only the process id", "CPU registers including the program counter", "The whole disk", "The page replacement algorithm"], 1, "Registers and the program counter are saved so the process can resume."),
    ("process", "advanced", "Which is true of threads in the same process?", ["They share one stack", "They share code, data and heap but have their own stacks", "They share nothing", "They have separate address spaces"], 1, "Threads share the address space but each has its own stack and registers."),
    ("sync", "beginner", "A race condition occurs when…", ["a thread is too slow", "the result depends on the interleaving of unsynchronised accesses to shared data", "two threads have the same name", "memory is full"], 1, "Unsynchronised shared access makes the outcome timing-dependent."),
    ("sync", "intermediate", "A counting semaphore initialised to 3 allows…", ["exactly one thread", "up to three threads at the same time", "only reading", "no threads"], 1, "Its value is the number of available units."),
    ("sync", "advanced", "Which breaks circular wait in dining philosophers?", ["Everyone takes the left fork first", "Taking forks in a global order", "Eating faster", "More philosophers"], 1, "Resource ordering makes a cycle of waiting impossible."),
    ("deadlock", "beginner", "Which is NOT a necessary condition for deadlock?", ["Mutual exclusion", "Hold and wait", "Preemption", "Circular wait"], 2, "The condition is NO preemption; if resources can be preempted deadlock can be broken."),
    ("deadlock", "intermediate", "In Banker's algorithm, Need equals…", ["Allocation − Maximum", "Maximum − Allocation", "Available − Allocation", "Maximum + Allocation"], 1, "Need = Maximum − Allocation."),
    ("deadlock", "advanced", "An unsafe state…", ["is always a deadlock", "may lead to deadlock but is not yet one", "can never lead to deadlock", "means no resources exist"], 1, "Unsafe means no safe sequence exists; deadlock is possible, not certain."),
    ("memory", "beginner", "Internal fragmentation is…", ["free memory between processes", "unused space inside an allocated block", "a full disk", "a slow CPU"], 1, "It is wasted space inside a partition given to a process."),
    ("memory", "intermediate", "Best fit chooses…", ["the first big-enough hole", "the smallest big-enough hole", "the largest hole", "a random hole"], 1, "Best fit picks the smallest sufficient hole."),
    ("memory", "advanced", "Compaction requires that processes can be…", ["swapped to tape", "relocated at run time", "deleted", "duplicated"], 1, "Moving processes needs dynamic relocation (base register update)."),
    ("paging", "beginner", "A page fault happens when…", ["the page is in memory", "the requested page is not in a frame", "the disk is full", "a process ends"], 1, "The page must be brought from disk."),
    ("paging", "intermediate", "Which page replacement algorithm is the theoretical best but unimplementable?", ["FIFO", "LRU", "Optimal", "Clock"], 2, "Optimal needs knowledge of future references."),
    ("paging", "advanced", "Belady's anomaly can occur with…", ["LRU", "Optimal", "FIFO", "none of them"], 2, "FIFO is not a stack algorithm, so more frames can cause more faults."),
    ("disk", "beginner", "Disk scheduling mainly tries to reduce…", ["CPU time", "head movement (seek time)", "memory size", "file size"], 1, "Less head movement means less seek time."),
    ("disk", "intermediate", "SCAN is also called…", ["the elevator algorithm", "the shortest seek algorithm", "the random algorithm", "the batch algorithm"], 0, "The head sweeps back and forth like an elevator."),
    ("disk", "advanced", "SSTF can suffer from…", ["starvation of far requests", "too much memory use", "deadlock", "fragmentation"], 0, "A stream of nearby requests can postpone distant ones indefinitely."),
    ("fs", "beginner", "Which allocation method stores each file in consecutive blocks?", ["Linked", "Indexed", "Contiguous", "Hashed"], 2, "Contiguous allocation uses one run of consecutive blocks."),
    ("fs", "intermediate", "Which allocation method has slow random access?", ["Contiguous", "Linked", "Indexed", "None"], 1, "Linked allocation must follow pointers from the start."),
    ("fs", "advanced", "Indexed allocation's main cost is…", ["external fragmentation", "an extra index block per file", "no direct access", "slower sequential reads"], 1, "Each file spends at least one block on its index."),
    ("vm", "beginner", "A virtual address is split into…", ["page number and offset", "frame and disk", "tag and set", "cylinder and head"], 0, "page = address // page size, offset = remainder."),
    ("vm", "intermediate", "A TLB caches…", ["disk blocks", "page-to-frame translations", "process ids", "file names"], 1, "It avoids a page-table lookup on a hit."),
    ("vm", "advanced", "Thrashing happens when…", ["a process has too many frames", "processes have fewer frames than their working sets", "the TLB is huge", "the disk is idle"], 1, "Constant faulting leaves little time for useful work."),
    ("perf", "beginner", "Which metric fits disk scheduling comparisons?", ["Page faults", "Total head movement", "Waiting time", "Fragmentation"], 1, "Seek distance is the disk-specific metric."),
    ("perf", "intermediate", "Why compare algorithms on identical workloads?", ["It is faster", "Differences then come from the algorithms, not the input", "Rules require it", "To hide results"], 1, "Different inputs would make the comparison meaningless."),
    ("perf", "advanced", "If Optimal has the fewest faults, a designer should…", ["always implement Optimal", "treat it as a lower bound to judge real algorithms", "ignore the data", "use FIFO"], 1, "Optimal needs the future, so it is a benchmark."),
]


PROVIDER = None          # set by app.auth.content.install(): admin-managed questions and hidden built-ins


def _rng(seed):
    return random.Random(seed)


def _cpu(level, seed):
    r = _rng(seed)
    n = {"beginner": 3, "intermediate": 4, "advanced": 4}[level]
    procs = [Process(f"P{i + 1}", r.randint(0, 4), r.randint(1, 7)) for i in range(n)]
    desc = ", ".join(f"{p.pid}(arrival {p.arrival}, burst {p.burst})" for p in procs)
    if level == "beginner":
        m = cpu_sim(procs, "fcfs").result["metrics"]
        return f"FCFS scheduling of {desc}. What is the average waiting time? (2 decimals)", m["avg_waiting_time"], 0.01, "Average of (turnaround − burst) over all processes."
    if level == "intermediate":
        m = cpu_sim(procs, "sjf").result["metrics"]
        return f"Non-preemptive SJF on {desc}. What is the average turnaround time? (2 decimals)", m["avg_turnaround_time"], 0.01, "Turnaround = completion − arrival; SJF picks the shortest ready burst each time."
    m = cpu_sim(procs, "rr", 2).result["metrics"]
    return f"Round Robin with quantum 2 on {desc}. How many context switches occur?", m["context_switches"], 0, "Count each time the CPU is given to a different process than the previous one."


def _proc(level, seed):
    r = _rng(seed)
    ps = [{"pid": f"P{i + 1}", "arrival": 0, "bursts": [r.randint(2, 6)]} for i in range({"beginner": 2, "intermediate": 3, "advanced": 3}[level])]
    q = {"beginner": 2, "intermediate": 2, "advanced": 3}[level]
    m = proc.simulate(ps, q).result["metrics"]
    d = ", ".join(f"{p['pid']} needs {p['bursts'][0]} ticks" for p in ps)
    return f"All processes arrive at time 0 and use Round Robin with quantum {q}: {d}. How many context switches happen?", m["context_switches"], 0, "A context switch occurs whenever a different process is dispatched than the one that ran last."


def _sync(level, seed):
    r = _rng(seed)
    t, n = r.randint(2, 3), r.randint(1, 2)
    res = run_scenario("race_condition", {"threads": t, "increments": n, "synchronized": level != "beginner", "quantum": 1})
    sy = "WITH a mutex" if level != "beginner" else "WITHOUT any lock"
    return (f"{t} threads each increment a shared counter {n} time(s) {sy}; the scheduler switches thread after every single operation (read, add, write each count as one). "
            f"What is the final counter value?"), res.result["shared"]["counter"], 0, "Trace the interleaving: without a lock, reads happen before earlier writes land and updates are lost."


def _deadlock(level, seed):
    r = _rng(seed)
    n, m = 3, 3
    alloc = [[r.randint(0, 2) for _ in range(m)] for _ in range(n)]
    mx = [[alloc[i][j] + r.randint(0, 3) for j in range(m)] for i in range(n)]
    av = [r.randint(0, 3) for _ in range(m)]
    fmt = lambda M: "; ".join(f"P{i}: {row}" for i, row in enumerate(M))
    body = f"Available {av}. Allocation → {fmt(alloc)}. Maximum → {fmt(mx)}."
    if level == "beginner":
        i, j = r.randrange(n), r.randrange(m)
        return f"{body} What is Need of P{i} for resource R{j}?", mx[i][j] - alloc[i][j], 0, "Need = Maximum − Allocation."
    res = dl.safety(av, alloc, mx).result
    if level == "intermediate":
        return f"{body} Is the state safe? Answer 1 for safe, 0 for unsafe.", int(res["safe"]), 0, "Run the safety algorithm: repeatedly finish any process whose Need ≤ Work."
    return f"{body} Using the safety algorithm (scan P0, P1, P2 each round), how many processes can finish before it gets stuck?", len(res["sequence"]), 0, "Count the safe-sequence length; if it is 3 the state is safe."


def _memory(level, seed):
    r = _rng(seed)
    blocks = [r.choice([100, 150, 200, 250, 300, 400, 500, 600]) for _ in range(5)]
    size = r.choice([90, 120, 180, 210, 260, 350])
    strat = {"beginner": "first_fit", "intermediate": "best_fit", "advanced": "worst_fit"}[level]
    tr = mem.simulate(blocks, [{"op": "alloc", "pid": "P", "size": size}], strat, "variable")
    last = tr.steps[-1]
    ans = last.state["chosen_start"] if last.event == "alloc" else -1
    return (f"Free partitions in address order (KB): {blocks} starting at address 0. A {size} KB process arrives. Using {mem.LABELS[strat]}, at which start address is it placed? "
            f"(answer -1 if it cannot be placed)"), ans, 0, "Addresses are cumulative sums of block sizes; apply the strategy to the holes that fit."


def _paging(level, seed):
    r = _rng(seed)
    refs = [r.randint(0, 5) for _ in range({"beginner": 10, "intermediate": 12, "advanced": 14}[level])]
    algo = {"beginner": "fifo", "intermediate": "lru", "advanced": "optimal"}[level]
    f = paging.simulate(refs, 3, algo).result["metrics"]["faults"]
    return f"Reference string {refs} with 3 frames. How many page faults does {paging.LABELS[algo]} produce?", f, 0, "Simulate frame by frame; the first references always fault."


def _disk(level, seed):
    r = _rng(seed)
    reqs = [r.randint(0, 199) for _ in range({"beginner": 5, "intermediate": 6, "advanced": 7}[level])]
    algo = {"beginner": "fcfs", "intermediate": "sstf", "advanced": "look"}[level]
    t = disk.simulate(reqs, 50, 199, "up", algo).result["metrics"]["total_head_movement"]
    extra = " (the head moves towards higher cylinders first)" if algo == "look" else ""
    return f"Head at cylinder 50, disk 0-199, requests {reqs}. What is the total head movement with {disk.LABELS[algo]}{extra}?", t, 0, "Sum the absolute distance between consecutive head positions."


def _fs(level, seed):
    r = _rng(seed)
    a, b, c = r.randint(2, 4), r.randint(1, 3), r.randint(1, 5)
    ops = [{"op": "create", "path": "/a", "size": a}, {"op": "create", "path": "/b", "size": b}, {"op": "delete", "path": "/a"}, {"op": "create", "path": "/c", "size": c}]
    tr = fs.simulate(16, "contiguous", ops, 1)
    start = next(f for f in tr.result["files"] if f["path"] == "/c")["blocks"][0]
    return (f"Contiguous allocation on a 16-block disk (1 KB blocks, first fit). Create /a of {a} KB, /b of {b} KB, delete /a, then create /c of {c} KB. "
            f"At which block does /c start?"), start, 0, "First fit takes the first run of free blocks that is long enough; the space freed by /a is reused only if it is large enough."


def _vm(level, seed):
    r = _rng(seed)
    ps = 1024 if level != "advanced" else 2048
    page, frame, off = r.randint(0, 7), r.randint(0, 15), r.randint(0, ps - 1)
    return f"Page size {ps} bytes. Virtual address {page * ps + off} is in page {page}, which is mapped to frame {frame}. What is the physical address?", frame * ps + off, 0, "physical = frame × page size + offset, where offset = address mod page size."


def _perf(level, seed):
    r = _rng(seed)
    refs = [r.randint(0, 5) for _ in range(12)]
    a, b = paging.simulate(refs, 3, "fifo").result["metrics"]["faults"], paging.simulate(refs, 3, "optimal").result["metrics"]["faults"]
    return f"Reference string {refs}, 3 frames. By how many faults does Optimal beat FIFO?", a - b, 0, "Subtract Optimal's faults from FIFO's; it is never negative."


GEN = {"cpu": _cpu, "process": _proc, "sync": _sync, "deadlock": _deadlock, "memory": _memory, "paging": _paging, "disk": _disk, "fs": _fs, "vm": _vm, "perf": _perf}
_ID = re.compile(r"^(m\|([a-z]+)\|(\d{1,3})|n\|([a-z]+)\|(beginner|intermediate|advanced)\|(\d{1,9}))$")


def build(module, level, n_numeric=2, seed=None):
    if module not in MOD_IDS:
        raise ValidationError(f"Unknown module '{module}'")
    if level not in LEVELS + ["all"]:
        raise ValidationError("level must be beginner, intermediate, advanced or all")
    levels = LEVELS if level == "all" else [level]
    qs = []
    for i, q in enumerate(MCQ):
        if q[0] == module and q[1] in levels:
            if PROVIDER and PROVIDER.is_hidden("question", f"m|{module}|{i}"):
                continue
            qs.append({"id": f"m|{module}|{i}", "type": "mcq", "level": q[1], "prompt": q[2], "options": q[3]})
    if PROVIDER:
        qs += PROVIDER.custom_mcq(module, levels)
    base = seed if seed is not None else random.SystemRandom().randrange(10 ** 8)
    for lv in levels:
        for k in range(n_numeric):
            s = base + k * 7919 + LEVELS.index(lv) * 104729
            prompt, _, _, _ = GEN[module](lv, s)
            qs.append({"id": f"n|{module}|{lv}|{s}", "type": "numeric", "level": lv, "prompt": prompt})
    return qs


_CUSTOM = re.compile(r"^c\|\d{1,9}$")


def _check(qid):
    if isinstance(qid, str) and _CUSTOM.match(qid):
        c = PROVIDER.get_custom(qid) if PROVIDER else None
        if not c:
            raise ValidationError(f"Invalid question id '{qid}'")
        return c
    m = _ID.match(qid) if isinstance(qid, str) else None
    if not m:
        raise ValidationError(f"Invalid question id '{qid}'")
    if m.group(1).startswith("m"):
        i = int(m.group(3))
        if i >= len(MCQ) or MCQ[i][0] != m.group(2):
            raise ValidationError(f"Invalid question id '{qid}'")
        q = MCQ[i]
        return {"type": "mcq", "level": q[1], "module": q[0], "answer": str(q[4]), "shown": q[3][q[4]], "explanation": q[5], "options": q[3]}
    mod, lv, seed = m.group(4), m.group(5), int(m.group(6))
    if mod not in GEN:
        raise ValidationError(f"Invalid question id '{qid}'")
    _, ans, tol, expl = GEN[mod](lv, seed)
    return {"type": "numeric", "level": lv, "module": mod, "answer": ans, "tol": tol, "shown": str(ans), "explanation": expl}


def grade(question_ids, answers):
    if not isinstance(question_ids, list) or not 1 <= len(question_ids) <= 60 or not isinstance(answers, dict):
        raise ValidationError("Provide the question ids you were shown (max 60) and your answers")
    res, score = [], 0
    for qid in question_ids:
        ch = _check(qid)
        given = answers.get(qid)
        ok = False
        if given is not None and str(given).strip() != "":
            if ch["type"] == "mcq":
                ok = str(given).strip() == ch["answer"]
            else:
                try:
                    ok = abs(float(str(given).strip()) - float(ch["answer"])) <= ch["tol"] + 1e-9
                except ValueError:
                    ok = False
        score += ok
        res.append({"id": qid, "correct": ok, "your_answer": None if given is None else str(given), "correct_answer": ch["shown"], "explanation": ch["explanation"], "level": ch["level"], "module": ch["module"]})
    by_level = {}
    for r in res:
        d = by_level.setdefault(r["level"], {"correct": 0, "total": 0})
        d["total"] += 1
        d["correct"] += r["correct"]
    return {"score": score, "total": len(res), "percent": round(100 * score / len(res), 1), "by_level": by_level, "results": res}
