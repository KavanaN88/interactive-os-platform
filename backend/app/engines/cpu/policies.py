"""Selection rules. Each policy owns its ready structure and answers two questions:
  select()    - who should hold the CPU right now (and why)?
  tick_done() - after one tick, did the running process finish / use up its quantum?
"""
from __future__ import annotations

from collections import deque


class QueuePolicy:
    """FCFS (quantum=None) and Round Robin: a single FIFO ready queue."""

    def __init__(self, rt, quantum=None):
        self.rt, self.quantum = rt, quantum
        self.q: deque[str] = deque()

    def admit(self, pid):
        self.q.append(pid)

    def ready(self):
        return list(self.q)

    def select(self, running, slice_used):
        if running is not None:
            return running, ""
        if not self.q:
            return None, ""
        pid = self.q.popleft()
        why = ("is at the head of the ready queue (first come, first served)" if self.quantum is None
               else f"is at the head of the ready queue and gets a quantum of {self.quantum}")
        return pid, f"{pid} {why}"

    def tick_done(self, running, finished, slice_used):
        if finished:
            return None, "", None
        if self.quantum is not None and slice_used >= self.quantum:
            self.q.append(running)
            return None, f"{running} used its full quantum ({self.quantum}); moved to the back of the ready queue", "quantum"
        return running, "", None


class SelectPolicy:
    """SJF, SRTF and Priority: pick the best candidate by a metric (lower is better).
    Ties are broken by earlier arrival, then input order, so results are deterministic."""

    def __init__(self, rt, metric, label, preemptive):
        self.rt, self.metric, self.label, self.preemptive = rt, metric, label, preemptive
        self.pool: list[str] = []

    def admit(self, pid):
        self.pool.append(pid)

    def ready(self):
        return sorted(self.pool, key=self._key)

    def _key(self, pid):
        r = self.rt[pid]
        return (self.metric(pid), r.arrival, r.idx)

    def _cands(self):
        return ", ".join(f"{p}={self.metric(p)}" for p in self.ready())

    def select(self, running, slice_used):
        if running is not None and not self.preemptive:
            return running, ""
        if not self.pool:
            return running, ""
        best = min(self.pool, key=self._key)
        if running is not None:
            if self.metric(running) <= self.metric(best):
                return running, ""
            self.pool.append(running)
            self.pool.remove(best)
            return best, (f"{best} has a better {self.label} ({self.metric(best)}) than the running "
                          f"{running} ({self.metric(running)}), so it preempts the CPU")
        cands = self._cands()
        self.pool.remove(best)
        return best, f"{best} has the best {self.label} among ready processes [{cands}]"

    def tick_done(self, running, finished, slice_used):
        return (None if finished else running), "", None


class MultiLevelPolicy:
    """MLQ (fixed queues) and MLFQ (feedback: demote on full quantum).
    Strict priority between levels: level 0 always runs first. A higher level
    becoming non-empty preempts a lower one; the preempted process returns to
    the FRONT of its own queue. A level quantum of None means FCFS."""

    def __init__(self, rt, levels, feedback):
        self.rt, self.levels, self.feedback = rt, levels, feedback
        self.queues = [deque() for _ in levels]
        self.level_of: dict[str, int] = {}

    def admit(self, pid):
        lvl = 0 if self.feedback else self.rt[pid].queue
        self.level_of[pid] = lvl
        self.queues[lvl].append(pid)

    def ready(self):
        return [p for q in self.queues for p in q]

    def _top(self):
        for i, q in enumerate(self.queues):
            if q:
                return i
        return None

    def select(self, running, slice_used):
        top = self._top()
        if running is not None:
            rl = self.level_of[running]
            if top is None or rl <= top:
                return running, ""
            self.queues[rl].appendleft(running)
            pid = self.queues[top].popleft()
            return pid, (f"{pid} from higher-priority queue {top} preempts {running} "
                         f"(queue {rl}); {running} returns to the front of its queue")
        if top is None:
            return None, ""
        pid = self.queues[top].popleft()
        return pid, f"{pid} is at the head of queue {top}, the highest non-empty queue"

    def tick_done(self, running, finished, slice_used):
        if finished:
            return None, "", None
        lvl = self.level_of[running]
        qn = self.levels[lvl]
        if qn is not None and slice_used >= qn:
            if self.feedback and lvl < len(self.levels) - 1:
                self.level_of[running] = lvl + 1
                self.queues[lvl + 1].append(running)
                return None, f"{running} used its full quantum ({qn}); demoted from queue {lvl} to queue {lvl + 1}", "demote"
            self.queues[lvl].append(running)
            return None, f"{running} used its full quantum ({qn}); moved to the back of queue {lvl}", "quantum"
        return running, "", None
