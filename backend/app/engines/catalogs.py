"""Descriptions served to the UI (so the frontend never hard-codes algorithm facts)."""
from app.engines.disk.engine import ALGORITHMS as DISK, LABELS as DISK_L
from app.engines.memory.engine import LABELS as MEM_L, STRATEGIES as MEM
from app.engines.paging.engine import ALGORITHMS as PAGING, LABELS as PAGING_L

PAGING_INFO = {
    "fifo": "Replaces the page that has been in memory the longest. Simple, but can evict heavily used pages and suffers Belady's anomaly.",
    "lru": "Replaces the page that was used least recently, assuming recent use predicts future use. A stack algorithm: no Belady's anomaly.",
    "optimal": "Replaces the page whose next use is farthest in the future. Gives the minimum possible faults but needs future knowledge, so it is a benchmark.",
    "lfu": "Replaces the page with the fewest references while resident (ties: oldest). Can keep stale pages that were once popular.",
    "clock": "Approximates LRU with a reference bit and a circular hand: pages with bit 1 get a second chance (bit cleared) before eviction.",
}
DISK_INFO = {
    "fcfs": "Services requests in arrival order. Fair, but the head may zig-zag across the disk.",
    "sstf": "Always services the closest pending request. Low movement, but far requests can starve.",
    "scan": "The head sweeps to the disk boundary servicing requests, then reverses (elevator).",
    "cscan": "Sweeps in one direction to the boundary, then jumps back and sweeps again; more uniform waiting time.",
    "look": "Like SCAN but reverses at the last pending request instead of the disk boundary.",
    "clook": "Like C-SCAN but jumps back from the last request to the farthest pending request.",
}
MEM_INFO = {
    "first_fit": "Takes the first hole large enough. Fast; tends to fragment the start of memory.",
    "best_fit": "Takes the smallest hole large enough. Leaves small leftover slivers.",
    "worst_fit": "Takes the largest hole, hoping the leftover stays useful. Often wastes big holes.",
}


def paging_catalog():
    return [{"id": a, "label": PAGING_L[a], "description": PAGING_INFO[a]} for a in PAGING]


def disk_catalog():
    return [{"id": a, "label": DISK_L[a], "description": DISK_INFO[a]} for a in DISK]


def memory_catalog():
    return [{"id": a, "label": MEM_L[a], "description": MEM_INFO[a]} for a in MEM]
