import { useState } from "react";
import { Layers, Loader2, Play } from "lucide-react";
import Card from "../components/Card";
import Kv from "../components/Kv";
import PageHeader from "../components/PageHeader";
import PlayerBar from "../components/PlayerBar";
import StepList from "../components/StepList";
import ComparePanel from "../components/ComparePanel";
import { BarsByFrames, FrameTable, HitMissTimeline } from "../components/visuals";
import { usePlayer } from "../hooks/usePlayer";
import { useCatalog } from "../hooks/useCatalog";
import { post } from "../lib/api";
import { parseIntList, toInt } from "../lib/parse";
import type { GCompare, GSim } from "../types";

const CLASSIC = "7,0,1,2,0,3,0,4,2,3,0,3,2,1,2,0,1,7,0,1";
const BELADY = "1,2,3,4,1,2,5,1,2,3,4,5";
interface BeladyRes { curve: { frames: number; faults: number }[]; anomaly: boolean; explanation: string; label: string }

export default function PageReplacement() {
  const { items, error: loadErr } = useCatalog("/page-replacement/algorithms");
  const [refsText, setRefsText] = useState(CLASSIC);
  const [frames, setFrames] = useState("3");
  const [algoId, setAlgoId] = useState("fifo");
  const [sim, setSim] = useState<GSim | null>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [belady, setBelady] = useState<BeladyRes | null>(null);
  const player = usePlayer(sim?.steps.length ?? 0);
  const algo = items.find((a) => a.id === algoId);
  const cur = sim?.steps[player.step];
  const input = () => ({ refs: parseIntList(refsText, "Reference string"), frames: toInt(frames, "Frames") });

  const start = async () => {
    setErr(""); setBusy(true);
    try { setSim(await post<GSim>("/page-replacement/simulate", { ...input(), algorithm: algoId })); player.load(); }
    catch (e) { setErr((e as Error).message); setSim(null); } finally { setBusy(false); }
  };
  const runBelady = async () => {
    setErr("");
    try { setBelady(await post<BeladyRes>("/page-replacement/belady", { refs: parseIntList(refsText, "Reference string"), algorithm: algoId, max_frames: 7 })); }
    catch (e) { setErr((e as Error).message); }
  };
  const m = sim?.result.metrics;

  return (
    <div className="max-w-[1500px] mx-auto">
      <PageHeader icon={<Layers size={26} />} title="Page Replacement Simulator" subtitle="See which page leaves memory when frames run out." tag={algo ? `Algorithm: ${algo.label}` : undefined} />
      {loadErr && <p className="mb-4 p-3 rounded-md border border-err/50 text-err text-sm">{loadErr}</p>}
      <div className="grid gap-4 xl:grid-cols-[340px_1fr_320px]">
        <Card title="Algorithm & Input">
          <div className="space-y-4 text-sm">
            <label className="block"><span className="text-mute">Algorithm</span>
              <select className="w-full mt-1" value={algoId} onChange={(e) => setAlgoId(e.target.value)}>{items.map((a) => <option key={a.id} value={a.id}>{a.label}</option>)}</select></label>
            <label className="block"><span className="text-mute">Reference string (comma or space separated)</span>
              <input className="w-full mt-1 font-mono" value={refsText} onChange={(e) => setRefsText(e.target.value)} /></label>
            <div className="flex gap-2 text-xs"><button className="border border-line rounded px-2 py-1 hover:bg-line/40" onClick={() => setRefsText(CLASSIC)}>Textbook string</button>
              <button className="border border-line rounded px-2 py-1 hover:bg-line/40" onClick={() => { setRefsText(BELADY); setFrames("3"); setAlgoId("fifo"); }}>Belady string</button></div>
            <label className="block"><span className="text-mute">Number of frames (1–16)</span><input className="w-full mt-1" inputMode="numeric" value={frames} onChange={(e) => setFrames(e.target.value)} /></label>
            <button onClick={start} disabled={busy} className="w-full flex items-center justify-center gap-2 bg-accent text-bg font-semibold rounded-md py-2.5">
              {busy ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}Start Simulation</button>
            <PlayerBar player={player} length={sim?.steps.length ?? 0} onReset={() => { setSim(null); player.stop(); setErr(""); }} />
            {err && <p className="text-err border border-err/40 rounded-md p-2">{err}</p>}
            {algo && <p className="text-xs text-mute leading-relaxed">{algo.description}</p>}
          </div>
        </Card>

        <div className="space-y-4 min-w-0">
          <Card title="Frame Table">
            {sim && cur ? <FrameTable refs={sim.result.refs} steps={sim.steps} upto={player.step} frames={sim.steps[0].state.frames.length} /> :
              <p className="text-sm text-mute py-8 text-center">Start a simulation to see each frame after every reference.</p>}
          </Card>
          {sim && <Card title="Hit / Fault Timeline"><HitMissTimeline timeline={sim.result.timeline} upto={player.step} /></Card>}
          {sim && cur && cur.state.ref_bits && (
            <Card title="Clock hand"><p className="text-sm font-mono">reference bits {JSON.stringify(cur.state.ref_bits)} · hand at frame {cur.state.pointer}</p></Card>
          )}
          <Card title="Step-by-Step Explanation">
            {sim ? <StepList steps={sim.steps} active={player.step} onSelect={player.jump} /> : <p className="text-sm text-mute">Each reference and the reason for any replacement appears here.</p>}
          </Card>
        </div>

        <div className="space-y-4">
          <Card title="Results">{m ? <Kv items={[["Page hits", m.hits], ["Page faults", m.faults], ["Hit ratio", `${m.hit_ratio}%`], ["Fault ratio", `${m.fault_ratio}%`], ["References", m.references]]} /> : <p className="text-sm text-mute">No results yet.</p>}</Card>
          <Card title="Belady's Anomaly Demo">
            <div className="space-y-3 text-sm">
              <p className="text-mute">Runs the selected algorithm on this reference string with 1–7 frames.</p>
              <button onClick={runBelady} className="border border-accent/50 text-accent rounded-md px-3 py-1.5 hover:bg-accent/10">Run demo</button>
              {belady && <><BarsByFrames curve={belady.curve} /><p className={belady.anomaly ? "text-err" : "text-ok"}>{belady.explanation}</p></>}
            </div>
          </Card>
        </div>
      </div>
      <Card title="Algorithm Comparison" className="mt-4">
        <ComparePanel columns={[["faults", "Faults", true], ["hit_ratio", "Hit %", false]]} barKey="faults" barLabel="Page faults"
          options={items} defaults={["fifo", "lru", "optimal"]}
          run={(ids) => post<GCompare>("/page-replacement/compare", { ...input(), algorithms: ids })} />
      </Card>
    </div>
  );
}
