"""Virtual file system: contiguous, linked and indexed allocation on a simulated disk of blocks.
Everything is in-memory data. Paths are validated against a strict pattern, so nothing here can reach the host's files.
Conventions: file size is in KB and rounded up to whole blocks; linked-list pointers and directory entries take no
extra space; indexed allocation uses one extra index block per file."""
from __future__ import annotations

import math
import re

from app.engines.errors import ValidationError
from app.engines.trace import SimulationTrace

METHODS = ["contiguous", "linked", "indexed"]
LABELS = {"contiguous": "Contiguous allocation", "linked": "Linked allocation", "indexed": "Indexed allocation"}
MAX_BLOCKS, MAX_OPS, MAX_DEPTH = 512, 200, 10
_SEG = re.compile(r"^[A-Za-z0-9_.-]{1,32}$")


def _int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def norm_path(path):
    if not isinstance(path, str) or not path.startswith("/") or len(path) > 200:
        raise ValidationError("Paths must start with '/' and be at most 200 characters")
    if path == "/":
        return "/"
    segs = path.strip("/").split("/")
    if len(segs) > MAX_DEPTH or any(not _SEG.match(s) or s in (".", "..") for s in segs):
        raise ValidationError(f"Invalid path '{path}': use up to {MAX_DEPTH} folders of letters, digits, '_', '-' or '.' (no '..')")
    return "/" + "/".join(segs)


def _parent(path):
    return path.rsplit("/", 1)[0] or "/"


def _validate(total_blocks, method, ops, bs):
    if method not in METHODS:
        raise ValidationError(f"Unknown method '{method}'. Supported: {', '.join(METHODS)}")
    if not _int(total_blocks) or not 4 <= total_blocks <= MAX_BLOCKS:
        raise ValidationError(f"Disk size must be 4..{MAX_BLOCKS} blocks")
    if not _int(bs) or not 1 <= bs <= 64:
        raise ValidationError("Block size must be 1..64 KB")
    if not isinstance(ops, list) or not 1 <= len(ops) <= MAX_OPS:
        raise ValidationError(f"Provide 1..{MAX_OPS} operations")
    for o in ops:
        if o.get("op") not in ("mkdir", "create", "delete", "read", "append"):
            raise ValidationError("Operations are: mkdir, create, delete, read, append")
        norm_path(o.get("path"))
        if o["op"] in ("create", "append") and (not _int(o.get("size")) or not 1 <= o["size"] <= 100_000):
            raise ValidationError(f"{o['op']} needs a size in KB (1-100000)")


def simulate(total_blocks, method, ops, block_size_kb=1) -> SimulationTrace:
    _validate(total_blocks, method, ops, block_size_kb)
    N = total_blocks
    owner: list[str | None] = [None] * N
    role: list[str | None] = [None] * N
    nxt: dict[int, int | None] = {}
    files: dict[str, dict] = {}
    dirs = {"/"}
    failed = 0
    trace = SimulationTrace("file_system", method, {"total_blocks": N, "ops": ops, "block_size_kb": block_size_kb})

    def runs():
        out, i = [], 0
        while i < N:
            if owner[i] is None:
                j = i
                while j < N and owner[j] is None:
                    j += 1
                out.append((i, j - i))
                i = j
            else:
                i += 1
        return out

    def frag(f):
        order = ([f["index_block"]] if f["index_block"] is not None else []) + f["blocks"]
        return 1 + sum(1 for a, b in zip(order, order[1:]) if b != a + 1) if order else 0

    def stats():
        free = N - sum(1 for o in owner if o)
        largest = max((l for _, l in runs()), default=0)
        used = N - free
        idx = sum(1 for r in role if r == "index")
        return {"total_blocks": N, "used_blocks": used, "free_blocks": free, "utilization_pct": round(100 * used / N, 2),
                "index_blocks": idx, "largest_free_run": largest,
                "external_fragmentation_pct": round((1 - largest / free) * 100, 2) if free else 0.0,
                "avg_fragments_per_file": round(sum(frag(f) for f in files.values()) / len(files), 2) if files else 0.0,
                "files": len(files), "directories": len(dirs) - 1}

    def tree(path="/"):
        kids = sorted({p for p in list(files) + list(dirs) if p != "/" and _parent(p) == path})
        node = {"name": "/" if path == "/" else path.rsplit("/", 1)[1], "path": path, "type": "dir", "children": []}
        for k in kids:
            if k in dirs:
                node["children"].append(tree(k))
            else:
                f = files[k]
                node["children"].append({"name": k.rsplit("/", 1)[1], "path": k, "type": "file", "size_kb": f["size"], "blocks": ([f["index_block"]] if f["index_block"] is not None else []) + f["blocks"]})
        return node

    def snap(extra=None):
        s = {"owners": list(owner), "roles": list(role), "next": {str(k): v for k, v in nxt.items()}, "tree": tree(), **stats(),
             "files_detail": [{"path": p, "size_kb": f["size"], "blocks": f["blocks"], "index_block": f["index_block"], "fragments": frag(f)} for p, f in files.items()]}
        if extra:
            s.update(extra)
        return s

    def alloc(n):
        """Return (data_blocks, index_block) or (None, reason)."""
        free_total = sum(1 for o in owner if o is None)
        need = n + (1 if method == "indexed" else 0)
        if free_total < need:
            return None, f"needs {need} block(s) but only {free_total} are free"
        if method == "contiguous":
            for s, l in runs():
                if l >= n:
                    return list(range(s, s + n)), None
            return None, f"needs {n} CONTIGUOUS blocks but the largest free run is only {max((l for _, l in runs()), default=0)} (external fragmentation, {free_total} blocks are free in total)"
        free_blocks = [i for i in range(N) if owner[i] is None]
        if method == "linked":
            return free_blocks[:n], None
        return free_blocks[1:n + 1], free_blocks[0]

    def mark(path, blocks, index_block):
        for b in blocks:
            owner[b], role[b] = path, "data"
        if index_block is not None:
            owner[index_block], role[index_block] = path, "index"
        if method == "linked":
            for a, b in zip(blocks, blocks[1:]):
                nxt[a] = b
            if blocks:
                nxt[blocks[-1]] = None

    trace.add(0, "init", "Format disk", f"{LABELS[method]} on a virtual disk of {N} blocks × {block_size_kb} KB. All blocks are free.", snap())
    for i, o in enumerate(ops, start=1):
        kind, path = o["op"], norm_path(o["path"])
        if kind == "mkdir":
            if path in dirs or path in files:
                failed += 1
                trace.add(i, "error", f"mkdir {path}", f"{path} already exists", snap())
            elif _parent(path) not in dirs:
                failed += 1
                trace.add(i, "error", f"mkdir {path}", f"Parent folder {_parent(path)} does not exist", snap())
            else:
                dirs.add(path)
                trace.add(i, "mkdir", f"mkdir {path}", f"Directory {path} created (directories only add an entry to the tree)", snap())
        elif kind == "create":
            n = max(1, math.ceil(o["size"] / block_size_kb))
            if path in dirs or path in files:
                failed += 1
                trace.add(i, "error", f"create {path}", f"{path} already exists", snap())
            elif _parent(path) not in dirs:
                failed += 1
                trace.add(i, "error", f"create {path}", f"Parent folder {_parent(path)} does not exist", snap())
            else:
                data, idx = alloc(n)
                if data is None:
                    failed += 1
                    trace.add(i, "alloc_failed", f"create {path}", f"Cannot create {path} ({o['size']} KB = {n} block(s)): it {idx}", snap())
                else:
                    files[path] = {"size": o["size"], "blocks": data, "index_block": idx}
                    mark(path, data, idx)
                    how = {"contiguous": f"first run of {n} consecutive free blocks: {data[0]}..{data[-1]}; directory stores start={data[0]}, length={n}",
                           "linked": f"blocks {data} are chained: each block stores a pointer to the next; directory stores first={data[0]}, last={data[-1]}",
                           "indexed": f"index block {idx} lists the data blocks {data}; directory stores the index block number"}[method]
                    trace.add(i, "create", f"create {path}", f"{path} ({o['size']} KB → {n} block(s)): {how}", snap({"disk_requests": ([idx] if idx is not None else []) + data}))
        elif kind == "delete":
            if path in files:
                f = files.pop(path)
                for b in f["blocks"] + ([f["index_block"]] if f["index_block"] is not None else []):
                    owner[b], role[b] = None, None
                    nxt.pop(b, None)
                trace.add(i, "delete", f"delete {path}", f"{path} deleted: directory entry removed and {len(f['blocks']) + (f['index_block'] is not None)} block(s) returned to the free list", snap())
            elif path in dirs and path != "/":
                if any(_parent(p) == path for p in list(files) + list(dirs)):
                    failed += 1
                    trace.add(i, "error", f"delete {path}", f"Directory {path} is not empty", snap())
                else:
                    dirs.discard(path)
                    trace.add(i, "delete", f"delete {path}", f"Directory {path} removed", snap())
            else:
                failed += 1
                trace.add(i, "error", f"delete {path}", f"{path} does not exist (or is the root)", snap())
        elif kind == "read":
            f = files.get(path)
            if not f:
                failed += 1
                trace.add(i, "error", f"read {path}", f"{path} is not a file", snap())
                continue
            b = f["blocks"]
            if method == "contiguous":
                acc, why = b, f"start={b[0]}, length={len(b)}: block k is at {b[0]}+k, so any block is reachable with ONE seek (direct access)"
            elif method == "linked":
                acc, why = b, f"follow the pointer chain {' → '.join(map(str, b))}; reaching block k requires reading all k blocks before it (slow random access)"
            else:
                acc, why = [f["index_block"]] + b, f"read index block {f['index_block']} first, then jump straight to any data block {b} (direct access, one extra read)"
            trace.add(i, "read", f"read {path}", f"Reading {path}: {why}", snap({"access": acc, "disk_requests": acc}))
        else:  # append
            f = files.get(path)
            if not f:
                failed += 1
                trace.add(i, "error", f"append {path}", f"{path} is not a file", snap())
                continue
            add = max(1, math.ceil(o["size"] / block_size_kb))
            if method == "contiguous":
                end = f["blocks"][-1] + 1
                if end + add > N or any(owner[b] is not None for b in range(end, end + add)):
                    failed += 1
                    trace.add(i, "alloc_failed", f"append {path}", f"{path} cannot grow in place: the {add} block(s) after block {f['blocks'][-1]} are not free. Contiguous files usually must be moved.", snap())
                    continue
                newb, idx = list(range(end, end + add)), None
            else:
                free_blocks = [b for b in range(N) if owner[b] is None]
                if len(free_blocks) < add:
                    failed += 1
                    trace.add(i, "alloc_failed", f"append {path}", f"Needs {add} block(s) but only {len(free_blocks)} are free", snap())
                    continue
                newb, idx = free_blocks[:add], None
            for b in newb:
                owner[b], role[b] = path, "data"
            if method == "linked":
                nxt[f["blocks"][-1]] = newb[0]
                for a, b2 in zip(newb, newb[1:]):
                    nxt[a] = b2
                nxt[newb[-1]] = None
            f["blocks"] += newb
            f["size"] += o["size"]
            trace.add(i, "append", f"append {path}", f"{path} grows by {add} block(s): {newb}" + (" (the pointer in the old last block is updated)" if method == "linked" else " (the index block gains new entries)" if method == "indexed" else ""), snap({"disk_requests": newb}))
    trace.result = {"algorithm_label": LABELS[method], "metrics": {**stats(), "failed_operations": failed}, "tree": tree(),
                    "files": [{"path": p, "size_kb": f["size"], "blocks": f["blocks"], "index_block": f["index_block"]} for p, f in files.items()]}
    return trace


def compare(total_blocks, ops, block_size_kb=1, methods=None):
    from app.engines.compare_util import summarize
    methods = methods or METHODS
    if len(methods) < 2 or len(set(methods)) != len(methods):
        raise ValidationError("Select at least two different methods to compare")
    runs = []
    for m in methods:
        tr = simulate(total_blocks, m, ops, block_size_kb)
        runs.append({"label": LABELS[m], "algorithm": m, "metrics": tr.result["metrics"]})
    best, notes = summarize(runs, {"failed_operations": ("failed operations", True), "utilization_pct": ("disk utilization %", False),
                                   "index_blocks": ("index-block overhead", True), "external_fragmentation_pct": ("external fragmentation %", True),
                                   "avg_fragments_per_file": ("fragments per file", True)})
    return {"runs": runs, "best_by_metric": best, "explanation": notes}
