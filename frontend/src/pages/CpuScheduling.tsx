import { useEffect, useMemo, useState } from "react";
import { Cpu, ListOrdered, BarChart3, Lightbulb, Settings2, Loader2 } from "lucide-react";
import Card from "../components/Card";
import GanttChart from "../components/GanttChart";
import InputPanel from "../components/InputPanel";
import StepList from "../components/StepList";
import ComparisonTab from "../components/ComparisonTab";
import { MetricsList, ResultsTable } from "../components/ResultsPanels";
import { api } from "../lib/api";
import { pidColor } from "../lib/colors";
import type { AlgoInfo, ProcessPayload, ProcessRow, SimResponse } from "../types";

const DEFAULT_ROWS: ProcessRow[] = [
  { pid: "P1", arrival: "0", burst: "5", priority: "2", queue: "0" },
  { pid: "P2", arrival: "1", burst: "4", priority: "1", queue: "0" },
  { pid: "P3", arrival: "2", burst: "6", priority: "3", queue: "1" },
];
const TABS = ["Simulation", "About", "Rules", "Comparison"] as const;
type Tab = (typeof TABS)[number];

function toInt(v: string, label: string): number {
  const n = Number(v);
  if (v.trim() === "" || !Number.isInteger(n)) throw new Error(`${label} must be a whole number`);
  return n;
}
function parseLevels(text: string): (number | null)[] | null {
  const parts = text.split(",").map((s) => s.trim().toLowerCase()).filter(Boolean);
  if (parts.length === 0) return null;
  return parts.map((s) => (s === "none" || s === "fcfs" ? null : toInt(s, "Queue quantum")));
}

export default function CpuScheduling() {
  const [algos, setAlgos] = useState<AlgoInfo[]>([]);
  const [algoId, setAlgoId] = useState("rr");
  const [quantum, setQuantum] = useState("2");
  const [levels, setLevels] = useState("");
  const [rows, setRows] = useState<ProcessRow[]>(DEFAULT_ROWS);
  const [tab, setTab] = useState<Tab>("Simulation");
  const [sim, setSim] = useState<SimResponse | null>(null);
  const [step, setStep] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [loadErr, setLoadErr] = useState("");

  useEffect(() => { api.algorithms().then(setAlgos).catch((e: Error) => setLoadErr(e.message)); }, []);
  const algo = useMemo(() => algos.find((a) => a.id === algoId), [algos, algoId]);

  // Build a request from the form; throws a readable Error on bad input.
  const buildProcesses = (needPriority: boolean, needQueue: boolean): ProcessPayload[] =>
    rows.map((r) => ({
      pid: r.pid.trim(),
      arrival: toInt(r.arrival, `${r.pid || "Process"} arrival`),
      burst: toInt(r.burst, `${r.pid || "Process"} burst`),
      priority: needPriority ? toInt(r.priority, `${r.pid} priority`) : 0,
      queue: needQueue ? toInt(r.queue, `${r.pid} queue`) : 0,
    }));

  const start = async () => {
    if (!algo) return;
    setErr(""); setBusy(true);
    try {
      const body = {
        algorithm: algo.id,
        processes: buildProcesses(algo.needs_priority, algo.needs_queue),
        quantum: algo.needs_quantum ? toInt(quantum, "Time quantum") : null,
        levels: algo.needs_levels ? parseLevels(levels) : null,
      };
      setSim(await api.simulate(body)); setStep(0); setPlaying(true);
    } catch (e) { setErr((e as Error).message); setSim(null); setPlaying(false); }
    finally { setBusy(false); }
  };
  const reset = () => { setSim(null); setStep(0); setPlaying(false); setErr(""); setRows(DEFAULT_ROWS); };

  const buildCompare = (ids: string[]) => {
    const chosen = ids.map((id) => algos.find((a) => a.id === id)!);
    return {
      processes: buildProcesses(chosen.some((a) => a.needs_priority), chosen.some((a) => a.needs_queue)),
      configs: chosen.map((a) => ({
        algorithm: a.id,
        quantum: a.needs_quantum ? toInt(quantum, "Time quantum") : null,
        levels: a.needs_levels ? parseLevels(levels) : null,
      })),
    };
  };

  // Autoplay only moves through the already-computed trace; speed changes timing, never results.
  useEffect(() => {
    if (!playing || !sim) return;
    if (step >= sim.steps.length - 1) { setPlaying(false); return; }
    const id = setTimeout(() => setStep((s) => s + 1), 1100 / speed);
    return () => clearTimeout(id);
  }, [playing, step, sim, speed]);

  const cur = sim?.steps[step];
  const order = sim?.result.processes.map((p) => p.pid) ?? [];
  const finished = !!sim && step >= sim.steps.length - 1;

  return (
    <div className="max-w-[1500px] mx-auto">
      <div className="flex flex-wrap items-center gap-3 mb-4">
        <div className="p-3 rounded-xl bg-accent/15 text-accent"><Cpu size={26} /></div>
        <div className="flex-1 min-w-[220px]">
          <h1 className="text-xl font-semibold">CPU Scheduling Simulator</h1>
          <p className="text-sm text-mute">Simulate and visualize CPU scheduling algorithms step by step.</p>
        </div>
        {algo && <span className="text-xs border border-line rounded-md px-3 py-1.5 text-mute">Algorithm: <b className="text-ink">{algo.label}</b></span>}
      </div>

      <div className="flex gap-1 border-b border-line mb-4">
        {TABS.map((t) => (
          <button key={t} onClick={() => setTab(t)} className={`px-4 py-2 text-sm rounded-t-md ${tab === t ? "bg-accent/15 text-accent" : "text-mute hover:text-ink"}`}>{t}</button>
        ))}
      </div>

      {loadErr && <p className="mb-4 p-3 rounded-md border border-err/50 text-err text-sm">{loadErr} — start the backend: <code>uvicorn app.main:app --reload</code></p>}
      {!algos.length && !loadErr && <p className="flex items-center gap-2 text-mute"><Loader2 className="animate-spin" size={16} />Loading algorithms…</p>}

      {algos.length > 0 && tab === "About" && algo && (
        <Card title={algo.label}><p className="text-sm leading-relaxed">{algo.description}</p></Card>
      )}
      {algos.length > 0 && tab === "Rules" && algo && (
        <Card title={`${algo.label} – rules`}><ul className="list-disc pl-5 space-y-2 text-sm">{algo.rules.map((r, i) => <li key={i}>{r}</li>)}</ul></Card>
      )}
      {algos.length > 0 && tab === "Comparison" && (
        <Card title="Algorithm Comparison" icon={<BarChart3 size={16} className="text-accent" />}><ComparisonTab algos={algos} build={buildCompare} /></Card>
      )}

      {algos.length > 0 && tab === "Simulation" && (
        <div className="grid gap-4 xl:grid-cols-[340px_1fr_330px]">
          <Card title="Algorithm & Input" icon={<Settings2 size={16} className="text-accent" />}>
            <InputPanel algos={algos} algo={algo} algoId={algoId} setAlgoId={setAlgoId} quantum={quantum} setQuantum={setQuantum}
              levels={levels} setLevels={setLevels} rows={rows} setRows={setRows}
              hasSim={!!sim} playing={playing} busy={busy} canPrev={!!sim && step > 0} canNext={!!sim && step < sim.steps.length - 1}
              speed={speed} setSpeed={setSpeed} onStart={start}
              onTogglePlay={() => { if (finished) setStep(0); setPlaying(!playing || finished); }}
              onPrev={() => { setPlaying(false); setStep((s) => Math.max(0, s - 1)); }}
              onNext={() => { setPlaying(false); setStep((s) => Math.min((sim?.steps.length ?? 1) - 1, s + 1)); }}
              onReset={reset} />
            {err && <p className="mt-3 text-sm text-err border border-err/40 rounded-md p-2">{err}</p>}
          </Card>

          <div className="space-y-4 min-w-0">
            <Card title="Execution Visualization" icon={<Cpu size={16} className="text-accent" />}>
              {!sim || !cur ? (
                <p className="text-sm text-mute py-10 text-center">Enter processes and press <b>Start Simulation</b> to see the Gantt chart.</p>
              ) : (
                <div className="space-y-4">
                  <p className="text-sm font-medium">Gantt Chart <span className="text-mute font-normal">({sim.result.algorithm_label}{algo?.needs_quantum ? `, q = ${quantum}` : ""})</span></p>
                  <GanttChart gantt={sim.result.gantt} makespan={sim.result.metrics.makespan} time={cur.time} order={order} />
                  <div className="grid sm:grid-cols-3 gap-3 text-sm">
                    <div className="border border-line rounded-lg p-3">
                      <p className="text-mute text-xs mb-2">Ready Queue (current)</p>
                      <div className="flex flex-wrap gap-1.5 min-h-[28px]">
                        {cur.state.ready.length === 0 ? <span className="text-mute text-xs">empty</span> :
                          cur.state.ready.map((p) => <span key={p} className="px-2.5 py-1 rounded text-xs font-semibold text-bg" style={{ background: pidColor(p, order) }}>{p}</span>)}
                      </div>
                    </div>
                    <div className="border border-line rounded-lg p-3">
                      <p className="text-mute text-xs mb-2">Running Process</p>
                      {cur.state.running ? <span className="px-2.5 py-1 rounded text-xs font-semibold text-bg" style={{ background: pidColor(cur.state.running, order) }}>{cur.state.running}</span> : <span className="text-mute text-xs">none</span>}
                    </div>
                    <div className="border border-line rounded-lg p-3">
                      <p className="text-mute text-xs mb-2">Simulation Time</p>
                      <p className="text-lg font-semibold font-mono">t = {cur.time} / {sim.result.metrics.makespan}</p>
                      <p className="text-[11px] text-mute mt-1">Completed: {cur.state.completed.join(", ") || "none"}</p>
                    </div>
                  </div>
                </div>
              )}
            </Card>

            <Card title={sim ? `Step-by-Step Execution (${step + 1} of ${sim.steps.length})` : "Step-by-Step Execution"} icon={<ListOrdered size={16} className="text-accent" />}>
              {sim ? <>
                <StepList steps={sim.steps} active={step} onSelect={(i) => { setPlaying(false); setStep(i); }} />
                {sim.truncated && <p className="text-xs text-warn mt-2">Showing the first {sim.steps.length} of {sim.total_steps} steps.</p>}
              </> : <p className="text-sm text-mute">Each scheduling decision and its reason will appear here.</p>}
            </Card>
          </div>

          <div className="space-y-4">
            <Card title="Results">{sim ? <ResultsTable rows={sim.result.processes} /> : <p className="text-sm text-mute">No results yet.</p>}</Card>
            <Card title="Performance Metrics">{sim ? <MetricsList m={sim.result.metrics} /> : <p className="text-sm text-mute">No results yet.</p>}</Card>
            <Card title="Observation" icon={<Lightbulb size={16} className="text-warn" />}>
              <p className="text-sm leading-relaxed">{cur ? cur.explanation : algo?.description}</p>
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}
