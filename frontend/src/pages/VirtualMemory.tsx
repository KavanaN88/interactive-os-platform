import { useState } from "react";
import { MemoryStick, Loader2, Play } from "lucide-react";
import Card from "../components/Card";
import Kv from "../components/Kv";
import PageHeader from "../components/PageHeader";
import PlayerBar from "../components/PlayerBar";
import StepList from "../components/StepList";
import Tabs from "../components/Tabs";
import ComparePanel from "../components/ComparePanel";
import { ValueBars, VmTables } from "../components/visuals2";
import { usePlayer } from "../hooks/usePlayer";
import { post } from "../lib/api";
import { parseIntList, toInt } from "../lib/parse";
import type { GCompare, GSim } from "../types";

const TABS = ["Address Translation", "Working Set", "Thrashing"] as const;
interface Ws { delta: number; rows: { t: number; page: number; working_set: number[]; size: number }[]; peak: number; average: number; explanation: string }
interface Th { rows: { processes: number; frames_per_process: number; faults_per_process: number; fault_rate: number; cpu_utilization: number }[]; peak_processes: number; thrashing_starts_at: number | null; explanation: string }

export default function VirtualMemory() {
  const [tab, setTab] = useState<(typeof TABS)[number]>("Address Translation");
  const [f, setF] = useState({ page: "1024", virt: "8192", phys: "4096", tlb: "2", tlbPol: "lru", repl: "lru", addrs: "0, 1024, 2500, 0, 3100, 5000, 7000, 2500, 100, 9000" });
  const [ws, setWs] = useState({ refs: "1,2,1,3,4,1,2,5,1,2,3,4,5,6,6,6,7,7", delta: "4" });
  const [th, setTh] = useState({ frames: "16", wss: "4", refs: "400", maxp: "12", cost: "50" });
  const [sim, setSim] = useState<GSim | null>(null);
  const [wsRes, setWsRes] = useState<Ws | null>(null);
  const [thRes, setThRes] = useState<Th | null>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const player = usePlayer(sim?.steps.length ?? 0);
  const cur = sim?.steps[player.step];
  const input = () => ({ page_size: toInt(f.page, "Page size"), virtual_size: toInt(f.virt, "Virtual memory"), physical_size: toInt(f.phys, "Physical memory"), tlb_size: toInt(f.tlb, "TLB size"), tlb_policy: f.tlbPol, addresses: parseIntList(f.addrs, "Addresses") });
  const run = async (fn: () => Promise<void>) => { setErr(""); setBusy(true); try { await fn(); } catch (e) { setErr((e as Error).message); } finally { setBusy(false); } };
  const start = () => {
    if (tab === "Address Translation") return run(async () => { setSim(await post<GSim>("/virtual-memory/translate", { ...input(), replacement: f.repl })); player.load(); });
    if (tab === "Working Set") return run(async () => setWsRes(await post<Ws>("/virtual-memory/working-set", { refs: parseIntList(ws.refs, "Reference string"), delta: toInt(ws.delta, "Window") })));
    return run(async () => setThRes(await post<Th>("/virtual-memory/thrashing", { total_frames: toInt(th.frames, "Total frames"), working_set_size: toInt(th.wss, "Working set"), refs_per_process: toInt(th.refs, "References"), max_processes: toInt(th.maxp, "Max processes"), fault_cost: toInt(th.cost, "Fault cost") })));
  };
  const m = sim?.result.metrics;
  const sel = (k: keyof typeof f, opts: string[]) => <select className="w-full mt-1" value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })}>{opts.map((o) => <option key={o}>{o}</option>)}</select>;
  const num = (label: string, v: string, set: (s: string) => void) => <label className="block"><span className="text-mute">{label}</span><input className="w-full mt-1" inputMode="numeric" value={v} onChange={(e) => set(e.target.value)} /></label>;

  return (
    <div className="max-w-[1500px] mx-auto">
      <PageHeader icon={<MemoryStick size={26} />} title="Virtual Memory Simulator" subtitle="Address translation, TLB, demand paging, working set and thrashing." />
      <Tabs tabs={TABS} value={tab} onChange={(t) => { setTab(t); setErr(""); }} />
      <div className="grid gap-4 xl:grid-cols-[340px_1fr_320px]">
        <Card title="Input">
          <div className="space-y-4 text-sm">
            {tab === "Address Translation" && <>
              <div className="grid grid-cols-2 gap-3">{num("Page size (bytes)", f.page, (v) => setF({ ...f, page: v }))}{num("TLB entries (0–16)", f.tlb, (v) => setF({ ...f, tlb: v }))}
                {num("Virtual memory (bytes)", f.virt, (v) => setF({ ...f, virt: v }))}{num("Physical memory (bytes)", f.phys, (v) => setF({ ...f, phys: v }))}</div>
              <div className="grid grid-cols-2 gap-3"><label className="block"><span className="text-mute">TLB policy</span>{sel("tlbPol", ["lru", "fifo"])}</label><label className="block"><span className="text-mute">Page replacement</span>{sel("repl", ["lru", "fifo"])}</label></div>
              <label className="block"><span className="text-mute">Virtual addresses</span><input className="w-full mt-1 font-mono" value={f.addrs} onChange={(e) => setF({ ...f, addrs: e.target.value })} /></label>
              <p className="text-[11px] text-mute">Try addresses outside 0–{Number(f.virt) - 1} to see an invalid access.</p></>}
            {tab === "Working Set" && <>
              <label className="block"><span className="text-mute">Reference string</span><input className="w-full mt-1 font-mono" value={ws.refs} onChange={(e) => setWs({ ...ws, refs: e.target.value })} /></label>
              {num("Window size Δ (last Δ references)", ws.delta, (v) => setWs({ ...ws, delta: v }))}</>}
            {tab === "Thrashing" && <>
              <div className="grid grid-cols-2 gap-3">{num("Total frames", th.frames, (v) => setTh({ ...th, frames: v }))}{num("Working set (pages)", th.wss, (v) => setTh({ ...th, wss: v }))}
                {num("References / process", th.refs, (v) => setTh({ ...th, refs: v }))}{num("Max processes", th.maxp, (v) => setTh({ ...th, maxp: v }))}</div>
              {num("Page-fault cost (memory accesses)", th.cost, (v) => setTh({ ...th, cost: v }))}</>}
            <button onClick={start} disabled={busy} className="w-full flex items-center justify-center gap-2 bg-accent text-bg font-semibold rounded-md py-2.5">{busy ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}{tab === "Address Translation" ? "Start Simulation" : "Run"}</button>
            {tab === "Address Translation" && <PlayerBar player={player} length={sim?.steps.length ?? 0} onReset={() => { setSim(null); player.stop(); setErr(""); }} />}
            {err && <p className="text-err border border-err/40 rounded-md p-2">{err}</p>}
          </div>
        </Card>

        <div className="space-y-4 min-w-0">
          {tab === "Address Translation" && <>
            <Card title="Translation">
              {cur && cur.event !== "init" ? <div className="space-y-3">
                <p className={`text-sm rounded-md border p-3 ${cur.event === "invalid" ? "border-err text-err" : cur.event === "page_fault" ? "border-warn text-warn" : cur.event === "tlb_hit" ? "border-ok text-ok" : "border-line"}`}>{cur.explanation}</p>
                <ol className="text-sm space-y-1 list-decimal pl-5">{(cur.state.actions as string[]).map((a, i) => <li key={i}>{a}</li>)}</ol></div>
                : <p className="text-sm text-mute py-6 text-center">Start a simulation and step through each address.</p>}
            </Card>
            {cur && <Card title="Page Table · TLB · Frames"><VmTables pageTable={cur.state.page_table} tlb={cur.state.tlb} frames={cur.state.frames} current={{ page: cur.state.page, frame: cur.state.frame }} /></Card>}
            <Card title="Step-by-Step Explanation">{sim ? <StepList steps={sim.steps} active={player.step} onSelect={player.jump} /> : <p className="text-sm text-mute">Each memory access and its outcome appears here.</p>}</Card></>}
          {tab === "Working Set" && <Card title="Working-set size over time">{wsRes ? <><ValueBars rows={wsRes.rows} valueKey="size" labelKey="t" /><p className="text-sm mt-3">{wsRes.explanation}</p>
            <div className="overflow-x-auto mt-3"><table className="w-full text-xs"><thead className="text-mute"><tr><th className="text-left">t</th><th>Page</th><th className="text-left">Working set</th></tr></thead><tbody>{wsRes.rows.map((r) => <tr key={r.t} className="border-t border-line"><td className="py-1">{r.t}</td><td className="text-center">{r.page}</td><td className="font-mono">{`{${r.working_set.join(", ")}}`}</td></tr>)}</tbody></table></div></> : <p className="text-sm text-mute py-8 text-center">Press Run to compute the working set at each reference.</p>}</Card>}
          {tab === "Thrashing" && <Card title="CPU utilization vs degree of multiprogramming">{thRes ? <><ValueBars rows={thRes.rows} valueKey="cpu_utilization" labelKey="processes" unit="%" mark={(r) => thRes.thrashing_starts_at !== null && r.processes >= thRes.thrashing_starts_at} />
            <p className="text-[11px] text-mute mt-1">Red bars: each process has fewer frames than its working set.</p><p className="text-sm mt-3">{thRes.explanation}</p>
            <div className="overflow-x-auto mt-3"><table className="w-full text-xs text-center"><thead className="text-mute"><tr><th>Processes</th><th>Frames each</th><th>Faults each</th><th>Fault %</th><th>CPU %</th></tr></thead><tbody>{thRes.rows.map((r) => <tr key={r.processes} className="border-t border-line"><td className="py-1">{r.processes}</td><td>{r.frames_per_process}</td><td>{r.faults_per_process}</td><td>{r.fault_rate}</td><td>{r.cpu_utilization}</td></tr>)}</tbody></table></div></> : <p className="text-sm text-mute py-8 text-center">Press Run to see utilisation rise, then collapse.</p>}</Card>}
        </div>

        <div className="space-y-4">
          {tab === "Address Translation" && <Card title="Results">{m ? <Kv items={[["Accesses", m.accesses], ["Invalid", m.invalid_accesses], ["TLB hits", m.tlb_hits], ["TLB misses", m.tlb_misses], ["TLB hit ratio", `${m.tlb_hit_ratio}%`], ["Page faults", m.page_faults], ["Fault rate", `${m.fault_rate}%`], ["Effective access time", `${m.effective_access_time_ns} ns`]]} /> : <p className="text-sm text-mute">No results yet.</p>}</Card>}
          {tab === "Working Set" && wsRes && <Card title="Summary"><Kv items={[["Window Δ", wsRes.delta], ["Peak working set", wsRes.peak], ["Average", wsRes.average]]} /></Card>}
          {tab === "Thrashing" && thRes && <Card title="Summary"><Kv items={[["Best at (processes)", thRes.peak_processes], ["Thrashing starts at", thRes.thrashing_starts_at ?? "never"]]} /></Card>}
        </div>
      </div>
      {tab === "Address Translation" && <Card title="Page Replacement Policy Comparison" className="mt-4">
        <ComparePanel columns={[["page_faults", "Page faults", true], ["tlb_hit_ratio", "TLB hit %", false], ["effective_access_time_ns", "EAT (ns)", true]]} barKey="page_faults" barLabel="Page faults"
          options={[{ id: "fifo", label: "FIFO" }, { id: "lru", label: "LRU" }]} defaults={["fifo", "lru"]} run={(ids) => post<GCompare>("/virtual-memory/compare", { ...input(), policies: ids })} /></Card>}
    </div>
  );
}
