import { useState } from "react";
import { Disc, Loader2, Play } from "lucide-react";
import Card from "../components/Card";
import Kv from "../components/Kv";
import PageHeader from "../components/PageHeader";
import PlayerBar from "../components/PlayerBar";
import StepList from "../components/StepList";
import ComparePanel from "../components/ComparePanel";
import { DiskTrack } from "../components/visuals";
import { usePlayer } from "../hooks/usePlayer";
import { useCatalog } from "../hooks/useCatalog";
import { post } from "../lib/api";
import { parseIntList, toInt } from "../lib/parse";
import type { GCompare, GSim } from "../types";

export default function DiskScheduling() {
  const { items, error: loadErr } = useCatalog("/disk/algorithms");
  const [reqText, setReqText] = useState("98,183,37,122,14,124,65,67");
  const [head, setHead] = useState("53");
  const [maxCyl, setMaxCyl] = useState("199");
  const [dir, setDir] = useState("up");
  const [countJump, setCountJump] = useState(true);
  const [algoId, setAlgoId] = useState("scan");
  const [sim, setSim] = useState<GSim | null>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const player = usePlayer(sim?.steps.length ?? 0);
  const algo = items.find((a) => a.id === algoId);
  const cur = sim?.steps[player.step];
  const input = () => ({ requests: parseIntList(reqText, "Request queue"), head: toInt(head, "Head position"), max_cylinder: toInt(maxCyl, "Max cylinder"), direction: dir, count_jump: countJump });

  const start = async () => {
    setErr(""); setBusy(true);
    try { setSim(await post<GSim>("/disk/simulate", { ...input(), algorithm: algoId })); player.load(); }
    catch (e) { setErr((e as Error).message); setSim(null); } finally { setBusy(false); }
  };
  const m = sim?.result.metrics;

  return (
    <div className="max-w-[1500px] mx-auto">
      <PageHeader icon={<Disc size={26} />} title="Disk Scheduling Simulator" subtitle="Watch the disk head service I/O requests." tag={algo ? `Algorithm: ${algo.label}` : undefined} />
      {loadErr && <p className="mb-4 p-3 rounded-md border border-err/50 text-err text-sm">{loadErr}</p>}
      <div className="grid gap-4 xl:grid-cols-[340px_1fr_320px]">
        <Card title="Algorithm & Input">
          <div className="space-y-4 text-sm">
            <label className="block"><span className="text-mute">Algorithm</span>
              <select className="w-full mt-1" value={algoId} onChange={(e) => setAlgoId(e.target.value)}>{items.map((a) => <option key={a.id} value={a.id}>{a.label}</option>)}</select></label>
            <label className="block"><span className="text-mute">Request queue (cylinders)</span><input className="w-full mt-1 font-mono" value={reqText} onChange={(e) => setReqText(e.target.value)} /></label>
            <div className="grid grid-cols-2 gap-3">
              <label className="block"><span className="text-mute">Head position</span><input className="w-full mt-1" inputMode="numeric" value={head} onChange={(e) => setHead(e.target.value)} /></label>
              <label className="block"><span className="text-mute">Max cylinder</span><input className="w-full mt-1" inputMode="numeric" value={maxCyl} onChange={(e) => setMaxCyl(e.target.value)} /></label>
            </div>
            <label className="block"><span className="text-mute">Initial direction (SCAN family)</span>
              <select className="w-full mt-1" value={dir} onChange={(e) => setDir(e.target.value)}><option value="up">Towards higher cylinders</option><option value="down">Towards lower cylinders</option></select></label>
            <label className="flex items-center gap-2 text-mute"><input type="checkbox" checked={countJump} onChange={(e) => setCountJump(e.target.checked)} className="!p-0" />Count the C-SCAN / C-LOOK return jump as head movement</label>
            <button onClick={start} disabled={busy} className="w-full flex items-center justify-center gap-2 bg-accent text-bg font-semibold rounded-md py-2.5">
              {busy ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}Start Simulation</button>
            <PlayerBar player={player} length={sim?.steps.length ?? 0} onReset={() => { setSim(null); player.stop(); setErr(""); }} />
            {err && <p className="text-err border border-err/40 rounded-md p-2">{err}</p>}
            {algo && <p className="text-xs text-mute leading-relaxed">{algo.description}</p>}
          </div>
        </Card>

        <div className="space-y-4 min-w-0">
          <Card title="Disk Head Movement">
            {sim ? <DiskTrack path={sim.result.head_path} maxCyl={Number(sim.input.max_cylinder)} requests={sim.input.requests as number[]} upto={player.step} /> :
              <p className="text-sm text-mute py-8 text-center">Start a simulation to see the head sweep across cylinders (time flows downward).</p>}
            {cur && <p className="text-sm mt-2">Head at cylinder <b className="font-mono">{cur.state.head}</b> · movement so far <b className="font-mono">{cur.state.total}</b></p>}
          </Card>
          <Card title="Step-by-Step Explanation">
            {sim ? <StepList steps={sim.steps} active={player.step} onSelect={player.jump} /> : <p className="text-sm text-mute">Why each request is chosen appears here.</p>}
          </Card>
        </div>

        <div className="space-y-4">
          <Card title="Results">{m ? <Kv items={[["Total head movement", m.total_head_movement], ["Average seek distance", m.avg_seek_distance], ["Requests", m.requests]]} /> : <p className="text-sm text-mute">No results yet.</p>}
            {sim && <p className="text-xs text-mute mt-3">Service order: <span className="font-mono">{sim.result.service_order.join(" → ")}</span></p>}</Card>
        </div>
      </div>
      <Card title="Algorithm Comparison" className="mt-4">
        <ComparePanel columns={[["total_head_movement", "Total movement", true], ["avg_seek_distance", "Avg seek", true]]} barKey="total_head_movement" barLabel="Total head movement"
          options={items} defaults={["fcfs", "sstf", "scan", "look"]}
          run={(ids) => post<GCompare>("/disk/compare", { ...input(), algorithms: ids })} />
      </Card>
    </div>
  );
}
