"""Which successful requests count as a 'simulation execution' in the admin statistics."""
import re

_USAGE = re.compile(r"^/api/v1/(cpu|page-replacement|disk|memory|deadlock|process|sync|filesystem|virtual-memory|analyzer|terminal)/"
                    r"(simulate|compare|run|translate|exec|safety|detect|recover|graph|request|ipc|threads|working-set|thrashing|belady|report)$")
MODULE_OF = {"cpu": "cpu", "page-replacement": "paging", "disk": "disk", "memory": "memory", "deadlock": "deadlock", "process": "process", "sync": "sync",
             "filesystem": "fs", "virtual-memory": "vm", "analyzer": "perf", "terminal": "terminal"}


def usage_for(method: str, path: str, status: int) -> tuple[str, str] | None:
    if method != "POST" or status != 200:
        return None
    m = _USAGE.match(path)
    return (MODULE_OF[m.group(1)], m.group(2)) if m else None
