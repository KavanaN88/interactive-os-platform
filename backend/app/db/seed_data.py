"""Static seed content. Pure Python (no DB imports) so it can be unit-tested anywhere."""
from app.engines.cpu.info import algorithm_catalog

ROLES = ["student", "administrator", "guest"]

# (slug, name, description, [algorithm names])  -- non-CPU algorithms are catalog entries only
MODULES = [
    ("cpu_scheduling", "CPU Scheduling", "How the OS picks which process runs on the CPU.", None),
    ("process_management", "Process Management", "Process lifecycle, PCBs, states, context switching, IPC.",
     ["Process Creation", "State Management", "Context Switching", "Process Termination", "IPC", "Multithreading"]),
    ("process_synchronization", "Process Synchronization", "Safe access to shared resources.",
     ["Mutex Lock", "Binary Semaphore", "Counting Semaphore", "Producer-Consumer", "Readers-Writers", "Dining Philosophers"]),
    ("deadlock_management", "Deadlock Management", "Deadlock avoidance, detection and recovery.",
     ["Banker's Algorithm", "Deadlock Detection", "Resource Allocation Graph", "Deadlock Recovery"]),
    ("memory_management", "Memory Management", "Allocating and freeing main memory.",
     ["First Fit", "Best Fit", "Worst Fit", "Paging", "Segmentation", "Compaction"]),
    ("page_replacement", "Page Replacement", "Choosing a victim page when frames are full.",
     ["FIFO", "LRU", "Optimal", "LFU", "Clock"]),
    ("disk_scheduling", "Disk Scheduling", "Ordering disk I/O requests to reduce seek time.",
     ["FCFS", "SSTF", "SCAN", "C-SCAN", "LOOK", "C-LOOK"]),
    ("file_system", "File System", "File organisation and block allocation.",
     ["Contiguous Allocation", "Linked Allocation", "Indexed Allocation"]),
    ("virtual_memory", "Virtual Memory", "Address translation, TLB, demand paging.",
     ["Address Translation", "TLB", "Demand Paging", "Thrashing", "Working Set Model"]),
    ("performance_analyzer", "Performance Analyzer", "Compare algorithms on identical workloads.", []),
]


def slugify(name: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in name.lower()).strip("_").replace("__", "_")


def algorithm_rows():
    """Yield (module_slug, algo_slug, name, description, rules, implemented)."""
    for slug, _name, _desc, names in MODULES:
        if slug == "cpu_scheduling":
            for a in algorithm_catalog():
                yield slug, a["id"], a["label"], a["description"], a["rules"], True
        else:
            for n in names or []:
                yield slug, slugify(n), n, "", [], False
