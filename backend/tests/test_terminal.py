import os, tempfile
from app.engines.errors import ValidationError
from app.engines.terminal.engine import execute, reset_sessions, MAX_SESSIONS, _SESSIONS
try:
    import pytest
except ImportError:
    from tests._shim import pytest

SID = "test-session-0001"

def run(line, sid=SID):
    return execute(sid, line)

def text(line, sid=SID):
    return "\n".join(run(line, sid)["output"])

def fresh():
    reset_sessions()

def test_help_lists_every_required_command():
    fresh()
    h = text("help")
    for c in ["os-info", "process list", "process create", "process terminate", "process status", "cpu status", "memory status", "disk status",
              "scheduler run", "deadlock check", "filesystem list", "filesystem create", "history", "clear"]:
        assert c in h, c
    assert "process create <pid> <burst>" in text("help process create")

def test_process_lifecycle_and_memory_integration():
    fresh()
    assert run("process create P1 5 1 100")["ok"] and run("process create P2 3 2 200")["ok"]
    assert "P1" in text("process list") and "ready" in text("process list")
    assert "allocated 300 KB" in text("memory status")
    assert "state     : ready" in text("process status P1")
    assert "released" in text("process terminate P1")
    ms = text("memory status")
    assert "allocated 200 KB" in ms and "P2" in ms and "P1" not in ms.split("Map:")[1].split("\n", 1)[1]

def test_scheduler_run_matches_cpu_engine_and_frees_memory():
    fresh()
    for cmd in ["process create P1 5", "process create P2 3", "process create P3 2"]:
        run(cmd)
    out = text("scheduler run fcfs")
    assert "[P1 0-5] [P2 5-8] [P3 8-10]" in out          # all created at t=0: waits 0,5,8 -> average 13/3
    assert "avg wait 4.3333" in out and "avg turnaround 7.6667" in out and "context switches 2" in out
    assert "terminated" in text("process list") and "allocated 0 KB" in text("memory status")
    assert not run("scheduler run fcfs")["ok"]          # nothing left to run

def test_scheduler_round_robin_quantum():
    fresh()
    run("process create A 4"); run("process create B 4")
    assert "[A 0-2] [B 2-4] [A 4-6] [B 6-8]" in text("scheduler run rr 2")

def test_out_of_memory_is_rejected_cleanly():
    fresh()
    assert run("process create BIG 5 1 1000")["ok"]
    r = run("process create TOO 5 1 100")
    assert not r["ok"] and "Cannot create TOO" in r["output"][0] and "TOO" not in text("process list")

def test_duplicate_and_unknown_processes():
    fresh()
    run("process create P1 5")
    assert "already exists" in text("process create P1 5")
    assert "No such process" in text("process status NOPE")
    assert run("process terminate P1")["ok"]
    assert "already terminated" in text("process terminate P1")

def test_filesystem_commands_and_disk_integration():
    fresh()
    assert run("filesystem mkdir /docs")["ok"]
    assert "Disk requests generated: 0 1 2" in text("filesystem create /docs/a.txt 3")
    assert "Disk requests generated: 3 4" in text("filesystem create /docs/b.txt 2")
    out = text("filesystem list /docs")
    assert "a.txt" in out and "b.txt" in out and "blocks [0, 1, 2]" in out and "blocks [3, 4]" in out
    assert "Blocks read, in order: 0 1 2" in text("filesystem read /docs/a.txt")
    ds = text("disk status")
    assert "5 used" in ds and "head at cylinder 2" in ds and "FCFS   total 10" in ds and "SSTF   total 4" in ds
    assert "b.txt deleted" in text("filesystem delete /docs/b.txt") and "b.txt" not in text("filesystem list /docs")

def test_filesystem_full_disk_and_format():
    fresh()
    assert not run("filesystem create /big 65")["ok"]
    run("filesystem create /f 4")
    assert "formatted" in text("filesystem format linked") and "(empty)" in text("filesystem list")
    assert "linked allocation" in text("os-info").lower()

def test_deadlock_scenarios():
    fresh()
    assert "SAFE, sequence <P1, P3, P0, P2, P4>" in text("deadlock check")
    run("deadlock load unsafe")
    out = text("deadlock check")
    assert "UNSAFE" in out and "no deadlock" in out and "warning" in out
    run("deadlock load deadlock")
    assert "DEADLOCK among P0, P1" in text("deadlock check")
    assert not run("deadlock load bogus")["ok"]

def test_cpu_status_and_history_and_clear():
    fresh()
    run("process create P1 7")
    assert "Pending CPU work    : 7 ticks" in text("cpu status")
    h = text("history")
    assert "process create P1 7" in h and "cpu status" in h
    assert run("clear")["clear"] is True

def test_sessions_are_isolated():
    fresh()
    run("process create P1 5", "session-aaaaaaaa")
    assert "No processes" in text("process list", "session-bbbbbbbb") and "State" not in text("process list", "session-bbbbbbbb")
    assert "ready" in text("process list", "session-aaaaaaaa")

# ------------------------------ security ------------------------------
INJECTIONS = ["ls; rm -rf /", "process list && whoami", "process list | cat", "$(id)", "`id`", "process list > /tmp/x", "echo $HOME", "process create P1 5; DROP TABLE users",
              "filesystem create /a\" 1", "process list\nwhoami", "python -c 'print(1)'", "process create P1 5 || reboot", "filesystem list *", "process status ~", "cmd /c dir"]

def test_shell_metacharacters_are_rejected_before_parsing():
    fresh()
    for bad in INJECTIONS:
        r = run(bad)
        assert not r["ok"] and r["output"], bad
        assert "Rejected" in r["output"][0] or "not found" in r["output"][0], bad

def test_real_commands_are_not_found():
    fresh()
    for cmd in ["ls", "cat /etc/passwd", "rm -rf /", "whoami", "sudo reboot", "python3", "dir", "del file", "curl http://x", "select * from users", "import os", "exec", "eval"]:
        r = run(cmd)
        assert not r["ok"] and ("not found" in r["output"][0] or "Rejected" in r["output"][0]), cmd

def test_path_traversal_and_host_paths_are_blocked():
    fresh()
    for p in ["/../etc/passwd", "/a/../../etc", "../x", "/etc/passwd/../shadow", "C:/Windows", "/a/./b"]:
        r = run(f"filesystem create {p} 1")
        assert not r["ok"], p
    r = run("filesystem read /etc/passwd")
    assert not r["ok"] and "not a file" in r["output"][0]
    assert not os.path.exists("/tmp/oslab-should-not-exist")

def test_no_host_side_effects_from_filesystem_commands():
    fresh()
    marker = os.path.join(tempfile.gettempdir(), "oslab_marker_file")
    run(f"filesystem create {marker} 1")                 # a real-looking absolute path: becomes a virtual name only
    assert not os.path.exists(marker)

def test_argument_bounds():
    fresh()
    for cmd in ["process create P1 0", "process create P1 99999", "process create P1 5 -1", "process create P1 abc", "process create P1", "process create too_long_pid_value_xx 5",
                "scheduler run magic", "filesystem create /a 0", "filesystem create /a 9999", "process create P1 5 1 5000"]:
        assert not run(cmd)["ok"], cmd

def test_input_and_session_limits():
    fresh()
    assert not run("a" * 500)["ok"]
    for bad in ["short", "bad id!", "x" * 100, ""]:
        with pytest.raises(ValidationError):
            execute(bad, "help")
    for i in range(MAX_SESSIONS + 20):
        execute(f"load-session-{i:05d}", "os-info")
    assert len(_SESSIONS) == MAX_SESSIONS

def test_process_table_is_bounded():
    fresh()
    for i in range(30):
        assert run(f"process create P{i} 1 1 1")["ok"]
    assert "full" in text("process create EXTRA 1 1 1")
