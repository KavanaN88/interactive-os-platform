import { useState } from "react";
import { Users, Loader2, Play, Plus, Trash2 } from "lucide-react";
import Card from "../components/Card";
import Kv from "../components/Kv";
import PageHeader from "../components/PageHeader";
import PlayerBar from "../components/PlayerBar";
import StepList from "../components/StepList";
import Tabs from "../components/Tabs";
import { BufferSlots, PcbTable, ProcessTree, StateDiagram, StateTimeline } from "../components/visuals2";
import { usePlayer } from "../hooks/usePlayer";
import { post } from "../lib/api";
import { parseIntList, parseIpcOps, toInt } from "../lib/parse";
import type { GSim } from "../types";

const TABS = ["Lifecycle", "IPC", "Threads"] as const;
type Row = { pid: string; arrival: string; bursts: string; priority: string; parent: string; memory: string };
const DEFAULT: Row[] = [
  { pid: "init", arrival: "0", bursts: "3,2,2", priority: "1", parent: "", memory: "64" },
  { pid: "shell", arrival: "1", bursts: "4,3,1", priority: "1", parent: "init", memory: "128" },
  { pid: "editor", arrival: "2", bursts: "5", priority: "2", parent: "shell", memory: "256" },
];
const IPC_DEFAULT: Record<string, string> = {
  pipe: "W send hello\nW send world\nW send again\nR recv\nR recv",
  message_queue: "R recv\nS send ping\nS send pong\nR recv",
  shared_memory: "A write x 1\nB write x 2\nA read x\nB read y",
};

export default function ProcessManagement() {
  const [tab, setTab] = useState<(typeof TABS)[number]>("Lifecycle");
  const [rows, setRows] = useState<Row[]>(DEFAULT);
  const [quantum, setQuantum] = useState("2");
  const [mech, setMech] = useState("pipe");
  const [cap, setCap] = useState("2");
  const [ipcText, setIpcText] = useState(IPC_DEFAULT.pipe);
  const [threads, setThreads] = useState("3");
  const [work, setWork] = useState("4");
  const [sim, setSim] = useState<GSim | null>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const player = usePlayer(sim?.steps.length ?? 0);
  const cur = sim?.steps[player.step];
  const upd = (i: number, k: keyof Row, v: string) => setRows(rows.map((r, j) => (j === i ? { ...r, [k]: v } : r)));

  const run = async (f: () => Promise<GSim>) => {
    setErr(""); setBusy(true);
    try { setSim(await f()); player.load(); } catch (e) { setErr((e as Error).message); setSim(null); } finally { setBusy(false); }
  };
  const start = () => {
    if (tab === "Lifecycle") return run(() => post<GSim>("/process/simulate", {
      quantum: toInt(quantum, "Quantum"),
      processes: rows.map((r) => ({ pid: r.pid.trim(), arrival: toInt(r.arrival, `${r.pid} arrival`), bursts: parseIntList(r.bursts, `${r.pid} bursts`), priority: toInt(r.priority, `${r.pid} priority`), parent: r.parent || null, memory: toInt(r.memory, `${r.pid} memory`) })) }));
    if (tab === "IPC") return run(() => post<GSim>("/process/ipc", { mechanism: mech, capacity: toInt(cap, "Capacity"), ops: parseIpcOps(ipcText, mech) }));
    return run(() => post<GSim>("/process/threads", { threads: toInt(threads, "Threads"), work: toInt(work, "Work") }));
  };
  const changeTab = (t: (typeof TABS)[number]) => { setTab(t); setSim(null); player.stop(); setErr(""); };
  const m = sim?.result.metrics;

  return (
    <div className="max-w-[1500px] mx-auto">
      <PageHeader icon={<Users size={26} />} title="Process Management Simulator" subtitle="Process lifecycle, PCBs, context switching, process tree, IPC and threads." />
      <Tabs tabs={TABS} value={tab} onChange={changeTab} />
      <div className="grid gap-4 xl:grid-cols-[360px_1fr_320px]">
        <Card title="Input">
          <div className="space-y-4 text-sm">
            {tab === "Lifecycle" && <>
              <label className="block"><span className="text-mute">Time quantum</span><input className="w-full mt-1" inputMode="numeric" value={quantum} onChange={(e) => setQuantum(e.target.value)} /></label>
              <div className="space-y-2">
                {rows.map((r, i) => (
                  <div key={i} className="border border-line rounded-md p-2 space-y-1.5">
                    <div className="flex gap-1.5"><input className="w-full min-w-0" value={r.pid} onChange={(e) => upd(i, "pid", e.target.value)} aria-label="PID" />
                      <button className="text-mute hover:text-err" disabled={rows.length <= 1} onClick={() => setRows(rows.filter((_, j) => j !== i))} aria-label="Remove"><Trash2 size={15} /></button></div>
                    <div className="grid grid-cols-2 gap-1.5 text-xs">
                      <label>Arrival<input className="w-full" value={r.arrival} onChange={(e) => upd(i, "arrival", e.target.value)} /></label>
                      <label>Priority<input className="w-full" value={r.priority} onChange={(e) => upd(i, "priority", e.target.value)} /></label>
                      <label className="col-span-2">Bursts (CPU, I/O, CPU…)<input className="w-full font-mono" value={r.bursts} onChange={(e) => upd(i, "bursts", e.target.value)} /></label>
                      <label>Parent<select className="w-full" value={r.parent} onChange={(e) => upd(i, "parent", e.target.value)}><option value="">none</option>{rows.slice(0, i).map((p) => <option key={p.pid}>{p.pid}</option>)}</select></label>
                      <label>Memory KB<input className="w-full" value={r.memory} onChange={(e) => upd(i, "memory", e.target.value)} /></label>
                    </div>
                  </div>))}
                <button className="inline-flex items-center gap-1 text-accent border border-accent/40 rounded-md px-3 py-1.5 hover:bg-accent/10" onClick={() => setRows([...rows, { pid: `P${rows.length + 1}`, arrival: "0", bursts: "3", priority: "1", parent: "", memory: "64" }])}><Plus size={15} />Add process</button>
              </div></>}
            {tab === "IPC" && <>
              <label className="block"><span className="text-mute">Mechanism</span><select className="w-full mt-1" value={mech} onChange={(e) => { setMech(e.target.value); setIpcText(IPC_DEFAULT[e.target.value]); setSim(null); }}>
                <option value="pipe">Pipe</option><option value="message_queue">Message queue</option><option value="shared_memory">Shared memory</option></select></label>
              {mech !== "shared_memory" && <label className="block"><span className="text-mute">Capacity</span><input className="w-full mt-1" value={cap} onChange={(e) => setCap(e.target.value)} /></label>}
              <label className="block"><span className="text-mute">Operations (one per line)</span>
                <textarea className="w-full mt-1 font-mono bg-bg border border-line rounded-md p-2 outline-none focus:border-accent" rows={8} value={ipcText} onChange={(e) => setIpcText(e.target.value)} />
                <span className="text-[11px] text-mute">{mech === "shared_memory" ? "A write x 5 · B read x" : "W send hello · R recv"}</span></label></>}
            {tab === "Threads" && <>
              <label className="block"><span className="text-mute">Threads (1–8)</span><input className="w-full mt-1" value={threads} onChange={(e) => setThreads(e.target.value)} /></label>
              <label className="block"><span className="text-mute">Work units per thread (1–20)</span><input className="w-full mt-1" value={work} onChange={(e) => setWork(e.target.value)} /></label></>}
            <button onClick={start} disabled={busy} className="w-full flex items-center justify-center gap-2 bg-accent text-bg font-semibold rounded-md py-2.5">{busy ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}Start Simulation</button>
            <PlayerBar player={player} length={sim?.steps.length ?? 0} onReset={() => { setSim(null); player.stop(); setErr(""); }} />
            {err && <p className="text-err border border-err/40 rounded-md p-2">{err}</p>}
          </div>
        </Card>

        <div className="space-y-4 min-w-0">
          {tab === "Lifecycle" && <>
            <Card title="Process State Diagram">{cur ? <StateDiagram processes={cur.state.processes} transition={cur.state.transition} /> : <p className="text-sm text-mute py-8 text-center">Start a simulation to watch processes move between states.</p>}</Card>
            {cur && <Card title="Process Control Blocks"><PcbTable processes={cur.state.processes} /></Card>}
            {cur?.state.context_switch && <Card title="Context Switch">
              <div className="grid sm:grid-cols-2 gap-3 text-sm">
                <div className="border border-line rounded-lg p-3"><p className="text-xs text-mute mb-1">Saved (leaving the CPU)</p><b>{cur.state.context_switch.saved.pid}</b><p className="font-mono text-xs mt-1">PC=0x{cur.state.context_switch.saved.regs.PC.toString(16)} SP=0x{cur.state.context_switch.saved.regs.SP.toString(16)}</p></div>
                <div className="border border-ok rounded-lg p-3"><p className="text-xs text-mute mb-1">Restored (taking the CPU)</p><b>{cur.state.context_switch.restored.pid}</b><p className="font-mono text-xs mt-1">PC=0x{cur.state.context_switch.restored.regs.PC.toString(16)} SP=0x{cur.state.context_switch.restored.regs.SP.toString(16)}</p></div></div></Card>}
            {sim && cur && <Card title="State Timeline"><StateTimeline timeline={sim.result.timeline} makespan={sim.result.metrics.makespan} upto={cur.time} /></Card>}
          </>}
          {tab === "IPC" && sim && cur && <Card title={`${mech.replace("_", " ")} state`}>
            {mech === "shared_memory"
              ? <div className="flex flex-wrap gap-2">{Object.entries(cur.state.memory as Record<string, unknown>).map(([k, v]) => <span key={k} className="border border-line rounded px-3 py-2 font-mono text-sm">{k} = {String(v)}</span>)}{Object.keys(cur.state.memory).length === 0 && <span className="text-mute text-sm">no slots written yet</span>}</div>
              : <BufferSlots items={cur.state.buffer} capacity={cur.state.capacity} />}
            {cur.state.blocked.length > 0 && <p className="text-sm text-err mt-3">Blocked: {cur.state.blocked.join(", ")}</p>}
            <p className="text-xs text-mute mt-3">{sim.result.description}</p></Card>}
          {tab === "Threads" && sim && cur && <Card title="Shared vs private">
            <p className="text-sm mb-2">Shared heap counter: <b className="font-mono">{cur.state.shared.heap_counter}</b></p>
            <table className="w-full text-sm text-center"><thead className="text-mute text-xs"><tr><th>Thread</th><th>Own stack: local_sum</th><th>SP</th><th>PC</th></tr></thead><tbody>
              {Object.entries(cur.state.stacks as Record<string, { local_sum: number; SP: number; PC: number }>).map(([k, s]) => <tr key={k} className={`border-t border-line ${cur.state.running === k ? "bg-accent/15" : ""}`}><td className="py-1.5">{k}</td><td>{s.local_sum}</td><td className="font-mono">0x{s.SP.toString(16)}</td><td className="font-mono">0x{s.PC.toString(16)}</td></tr>)}</tbody></table>
            <p className="text-xs text-mute mt-3">{sim.result.explanation}</p></Card>}
          <Card title="Step-by-Step Explanation">{sim ? <StepList steps={sim.steps} active={player.step} onSelect={player.jump} /> : <p className="text-sm text-mute">Every state change and its reason appears here.</p>}</Card>
        </div>

        <div className="space-y-4">
          {tab === "Lifecycle" && <>
            <Card title="Metrics">{m ? <Kv items={[["Makespan", m.makespan], ["Context switches", m.context_switches], ["CPU utilization", `${m.cpu_utilization}%`], ["Avg turnaround", m.avg_turnaround], ["Avg response", m.avg_response]]} /> : <p className="text-sm text-mute">No results yet.</p>}</Card>
            {sim && <Card title="Process Tree"><ProcessTree nodes={sim.result.tree} /></Card>}
            {sim && <Card title="State transitions"><Kv items={Object.entries(sim.result.transitions as Record<string, number>).map(([k, v]) => [k.replace("->", " → "), v])} /></Card>}</>}
          {tab !== "Lifecycle" && sim && <Card title="Summary">{tab === "IPC" ? <Kv items={[["Operations", m.operations], ["Blocked at end", m.blocked_at_end], ["Violations", m.violations]]} /> : <p className="text-sm text-mute">{sim.result.explanation}</p>}</Card>}
        </div>
      </div>
    </div>
  );
}
