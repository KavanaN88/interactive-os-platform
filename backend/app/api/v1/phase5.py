"""Routers for Process Management, Synchronization, File System, Virtual Memory, Analyzer, Terminal, Learn and Quiz."""
from fastapi import APIRouter, Depends, HTTPException

from app.api.v1.common import engine_errors, trace_payload
from app.api.v1.deps import optional_user
from app.auth import content, service
from app.engines.analyzer import engine as analyzer_engine
from app.engines.fs import engine as fs_engine
from app.engines.learn import quiz as quiz_engine
from app.engines.learn.content import MODULES
from app.engines.process import engine as process_engine
from app.engines.sync import scenarios
from app.engines.terminal import engine as terminal_engine
from app.engines.vm import engine as vm_engine
from app.schemas import modules as S

process = APIRouter(prefix="/process", tags=["process-management"])
sync = APIRouter(prefix="/sync", tags=["process-synchronization"])
filesystem = APIRouter(prefix="/filesystem", tags=["file-system"])
vm = APIRouter(prefix="/virtual-memory", tags=["virtual-memory"])
analyzer = APIRouter(prefix="/analyzer", tags=["performance-analyzer"])
terminal = APIRouter(prefix="/terminal", tags=["terminal"])
learn = APIRouter(prefix="/learn", tags=["learning-center"])
quiz = APIRouter(prefix="/quiz", tags=["quiz"])


@process.post("/simulate")
def p_simulate(req: S.ProcSimulate):
    with engine_errors():
        return trace_payload(process_engine.simulate([p.model_dump() for p in req.processes], req.quantum))


@process.post("/ipc")
def p_ipc(req: S.IpcRequest):
    with engine_errors():
        return trace_payload(process_engine.ipc(req.mechanism, [o.model_dump(exclude_none=True) for o in req.ops], req.capacity))


@process.post("/threads")
def p_threads(req: S.ThreadsRequest):
    with engine_errors():
        return trace_payload(process_engine.threads_demo(req.threads, req.work))


@sync.get("/scenarios")
def s_catalog():
    return scenarios.catalog()


@sync.post("/run")
def s_run(req: S.SyncRun):
    with engine_errors():
        return trace_payload(scenarios.run_scenario(req.scenario, req.params))


@filesystem.post("/simulate")
def f_simulate(req: S.FsSimulate):
    with engine_errors():
        return trace_payload(fs_engine.simulate(req.total_blocks, req.method, [o.model_dump(exclude_none=True) for o in req.ops], req.block_size_kb))


@filesystem.post("/compare")
def f_compare(req: S.FsCompare):
    with engine_errors():
        return fs_engine.compare(req.total_blocks, [o.model_dump(exclude_none=True) for o in req.ops], req.block_size_kb, req.methods)


@vm.post("/translate")
def v_translate(req: S.VmTranslate):
    with engine_errors():
        return trace_payload(vm_engine.translate(req.page_size, req.virtual_size, req.physical_size, req.addresses, req.tlb_size, req.tlb_policy, req.replacement))


@vm.post("/compare")
def v_compare(req: S.VmCompare):
    with engine_errors():
        return vm_engine.compare(req.page_size, req.virtual_size, req.physical_size, req.addresses, req.tlb_size, req.tlb_policy, req.policies)


@vm.post("/working-set")
def v_ws(req: S.WorkingSetRequest):
    with engine_errors():
        return vm_engine.working_set(req.refs, req.delta)


@vm.post("/thrashing")
def v_thrash(req: S.ThrashingRequest):
    with engine_errors():
        return vm_engine.thrashing(req.total_frames, req.working_set_size, req.refs_per_process, req.max_processes, req.fault_cost)


@analyzer.get("/catalog")
def a_catalog():
    return analyzer_engine.catalog()


@analyzer.post("/compare")
def a_compare(req: S.AnalyzerRequest):
    with engine_errors():
        return analyzer_engine.compare(req.module, req.workload, req.algorithms)


@analyzer.post("/report")
def a_report(req: S.AnalyzerRequest):
    with engine_errors():
        return analyzer_engine.report(req.module, req.workload, req.algorithms)


@terminal.post("/exec")
def t_exec(req: S.TerminalRequest):
    with engine_errors():
        return terminal_engine.execute(req.session_id, req.command)


@learn.get("/modules")
def l_modules():
    visible = content.topics()
    return [{"id": m, "name": n, "topics": sum(t["module"] == m for t in visible)} for m, n in MODULES]


@learn.get("/topics")
def l_topics(module: str | None = None):
    return [{k: t[k] for k in ("id", "module", "level", "title", "summary")} for t in content.topics(module)]


@learn.get("/topics/{topic_id}")
def l_topic(topic_id: str):
    t = content.topic(topic_id)
    if t is None:
        raise HTTPException(status_code=404, detail="Topic not found")
    return t


@quiz.get("/{module}")
def q_build(module: str, level: str = "all"):
    with engine_errors():
        return {"module": module, "level": level, "questions": quiz_engine.build(module, level)}


@quiz.post("/grade")
def q_grade(req: S.QuizGrade, user: dict | None = Depends(optional_user)):
    with engine_errors():
        graded = quiz_engine.grade(req.question_ids, req.answers)
    try:   # analytics must never break grading
        service.record_quiz_attempt(user["id"] if isinstance(user, dict) else None, graded["results"][0]["module"], req.level or "mixed", graded)
    except Exception:
        pass
    return graded
