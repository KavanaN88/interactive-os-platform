import { useState } from "react";
import { HardDrive, Loader2, Play } from "lucide-react";
import Card from "../components/Card";
import Kv from "../components/Kv";
import PageHeader from "../components/PageHeader";
import PlayerBar from "../components/PlayerBar";
import StepList from "../components/StepList";
import ComparePanel from "../components/ComparePanel";
import { MemoryMap } from "../components/visuals";
import { usePlayer } from "../hooks/usePlayer";
import { useCatalog } from "../hooks/useCatalog";
import { post } from "../lib/api";
import { parseIntList, parseOps } from "../lib/parse";
import type { GCompare, GSim } from "../types";

const BASIC = { blocks: "100,500,200,300,600", ops: "alloc P1 212\nalloc P2 417\nalloc P3 112\nalloc P4 426", mode: "variable" };
const COMPACT = { blocks: "100,100,100,100", ops: "alloc A 100\nalloc B 100\nalloc C 100\nalloc D 100\nfree A\nfree C\nalloc E 150   # fails: free space is split\ncompact\nalloc E 150", mode: "variable" };

export default function MemoryManagement() {
  const { items, error: loadErr } = useCatalog("/memory/strategies");
  const [blocks, setBlocks] = useState(BASIC.blocks);
  const [ops, setOps] = useState(BASIC.ops);
  const [mode, setMode] = useState(BASIC.mode);
  const [strategy, setStrategy] = useState("first_fit");
  const [sim, setSim] = useState<GSim | null>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const player = usePlayer(sim?.steps.length ?? 0);
  const strat = items.find((a) => a.id === strategy);
  const cur = sim?.steps[player.step];
  const input = () => ({ blocks: parseIntList(blocks, "Memory blocks"), ops: parseOps(ops), mode });
  const load = (p: typeof BASIC) => { setBlocks(p.blocks); setOps(p.ops); setMode(p.mode); setSim(null); player.stop(); };

  const start = async () => {
    setErr(""); setBusy(true);
    try { setSim(await post<GSim>("/memory/simulate", { ...input(), strategy })); player.load(); }
    catch (e) { setErr((e as Error).message); setSim(null); } finally { setBusy(false); }
  };
  const order: string[] = sim ? Array.from(new Set((sim.input.ops as { pid?: string }[]).map((o) => o.pid).filter((p): p is string => !!p))) : [];
  const s = cur?.state;

  return (
    <div className="max-w-[1500px] mx-auto">
      <PageHeader icon={<HardDrive size={26} />} title="Memory Management Simulator" subtitle="Contiguous allocation, fragmentation and compaction." tag={strat ? `Strategy: ${strat.label}` : undefined} />
      {loadErr && <p className="mb-4 p-3 rounded-md border border-err/50 text-err text-sm">{loadErr}</p>}
      <div className="grid gap-4 xl:grid-cols-[340px_1fr_320px]">
        <Card title="Strategy & Input">
          <div className="space-y-4 text-sm">
            <label className="block"><span className="text-mute">Placement strategy</span>
              <select className="w-full mt-1" value={strategy} onChange={(e) => setStrategy(e.target.value)}>{items.map((a) => <option key={a.id} value={a.id}>{a.label}</option>)}</select></label>
            <label className="block"><span className="text-mute">Partitioning</span>
              <select className="w-full mt-1" value={mode} onChange={(e) => setMode(e.target.value)}>
                <option value="variable">Variable (holes are split)</option><option value="fixed">Fixed (one process per partition)</option></select></label>
            <label className="block"><span className="text-mute">Initial memory blocks (KB, in address order)</span><input className="w-full mt-1 font-mono" value={blocks} onChange={(e) => setBlocks(e.target.value)} /></label>
            <label className="block"><span className="text-mute">Operations (one per line)</span>
              <textarea className="w-full mt-1 font-mono text-sm bg-bg border border-line rounded-md p-2 outline-none focus:border-accent" rows={7} value={ops} onChange={(e) => setOps(e.target.value)} />
              <span className="text-[11px] text-mute">alloc PID SIZE · free PID · compact (variable only)</span></label>
            <div className="flex gap-2 text-xs"><button className="border border-line rounded px-2 py-1 hover:bg-line/40" onClick={() => load(BASIC)}>Textbook example</button>
              <button className="border border-line rounded px-2 py-1 hover:bg-line/40" onClick={() => load(COMPACT)}>Compaction demo</button></div>
            <button onClick={start} disabled={busy} className="w-full flex items-center justify-center gap-2 bg-accent text-bg font-semibold rounded-md py-2.5">
              {busy ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}Start Simulation</button>
            <PlayerBar player={player} length={sim?.steps.length ?? 0} onReset={() => { setSim(null); player.stop(); setErr(""); }} />
            {err && <p className="text-err border border-err/40 rounded-md p-2">{err}</p>}
            {strat && <p className="text-xs text-mute leading-relaxed">{strat.description}</p>}
          </div>
        </Card>

        <div className="space-y-4 min-w-0">
          <Card title="Memory Map">
            {s ? <>
              <MemoryMap segments={s.segments} order={order} highlight={s.chosen_start} />
              {s.examined && <div className="mt-3 text-xs"><p className="text-mute mb-1">Holes examined</p>
                <div className="flex flex-wrap gap-1.5">{(s.examined as { start: number; size: number; fits: boolean }[]).map((h) => (
                  <span key={h.start} className={`px-2 py-1 rounded border ${h.fits ? "border-ok text-ok" : "border-line text-mute"}`}>{h.size} KB @ {h.start} {h.fits ? "fits" : "too small"}</span>))}</div></div>}
              <p className="text-[11px] text-mute mt-2">Striped = free · red strip = internal fragmentation inside a fixed partition</p>
            </> : <p className="text-sm text-mute py-8 text-center">Start a simulation to see memory after every operation.</p>}
          </Card>
          <Card title="Step-by-Step Explanation">
            {sim ? <StepList steps={sim.steps} active={player.step} onSelect={player.jump} /> : <p className="text-sm text-mute">Why each block is chosen appears here.</p>}
          </Card>
        </div>

        <div className="space-y-4">
          <Card title="Memory Statistics">{s ? <Kv items={[["Total memory", `${s.total_memory} KB`], ["Allocated", `${s.allocated_memory} KB`], ["Free", `${s.free_memory} KB`], ["Largest hole", `${s.largest_hole} KB`], ["Holes", s.hole_count],
            ["Internal fragmentation", `${s.internal_fragmentation} KB`], ["External fragmentation", `${s.external_fragmentation_pct}%`], ["Utilization", `${s.utilization_pct}%`]]} /> : <p className="text-sm text-mute">No results yet.</p>}</Card>
          {sim && player.step === sim.steps.length - 1 && (
            <Card title="Final Outcome"><Kv items={[["Failed allocations", sim.result.metrics.failed_allocations], ["…due to external fragmentation", sim.result.metrics.external_failures]]} /></Card>)}
        </div>
      </div>
      <Card title="Strategy Comparison" className="mt-4">
        <ComparePanel columns={[["failed_allocations", "Failed", true], ["utilization_pct", "Utilization %", false], ["internal_fragmentation", "Internal frag", true], ["largest_hole", "Largest hole", false]]}
          barKey="utilization_pct" barLabel="Memory utilization %" options={items} defaults={["first_fit", "best_fit", "worst_fit"]}
          run={(ids) => post<GCompare>("/memory/compare", { ...input(), strategies: ids })} />
      </Card>
    </div>
  );
}
