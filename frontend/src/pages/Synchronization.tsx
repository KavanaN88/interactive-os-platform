import { useEffect, useState } from "react";
import { GitMerge, Loader2, Play, Scale } from "lucide-react";
import Card from "../components/Card";
import Kv from "../components/Kv";
import PageHeader from "../components/PageHeader";
import PlayerBar from "../components/PlayerBar";
import StepList from "../components/StepList";
import { SyncState } from "../components/visuals2";
import { usePlayer } from "../hooks/usePlayer";
import { get, post } from "../lib/api";
import { toInt } from "../lib/parse";
import type { GSim } from "../types";

interface Param { name: string; label: string; type: "int" | "bool" | "choice"; default: number | boolean | string; min?: number; max?: number; options?: string[] }
interface Scenario { id: string; title: string; description: string; params: Param[] }

export default function Synchronization() {
  const [catalog, setCatalog] = useState<Scenario[]>([]);
  const [sid, setSid] = useState("race_condition");
  const [vals, setVals] = useState<Record<string, string | boolean>>({});
  const [sim, setSim] = useState<GSim | null>(null);
  const [pair, setPair] = useState<{ label: string; metrics: Record<string, number>; explanation: string }[] | null>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const player = usePlayer(sim?.steps.length ?? 0);
  const sc = catalog.find((c) => c.id === sid);
  const cur = sim?.steps[player.step];

  useEffect(() => { get<Scenario[]>("/sync/scenarios").then(setCatalog).catch((e: Error) => setErr(e.message)); }, []);
  useEffect(() => {
    if (!sc) return;
    setVals(Object.fromEntries(sc.params.map((p) => [p.name, p.type === "bool" ? (p.default as boolean) : String(p.default)])));
    setSim(null); setPair(null); player.stop();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sid, catalog.length]);

  const body = (over: Record<string, boolean> = {}) => ({
    scenario: sid,
    params: Object.fromEntries((sc?.params ?? []).map((p) => [p.name, p.name in over ? over[p.name] : p.type === "int" ? toInt(String(vals[p.name]), p.label) : vals[p.name]])),
  });
  const run = async () => {
    setErr(""); setBusy(true); setPair(null);
    try { setSim(await post<GSim>("/sync/run", body())); player.load(); } catch (e) { setErr((e as Error).message); setSim(null); } finally { setBusy(false); }
  };
  const runBoth = async () => {
    setErr(""); setBusy(true);
    try {
      const [bad, good] = await Promise.all([post<GSim>("/sync/run", body({ synchronized: false })), post<GSim>("/sync/run", body({ synchronized: true }))]);
      setPair([{ label: "Without synchronization", metrics: bad.result.metrics, explanation: bad.result.explanation }, { label: "With synchronization", metrics: good.result.metrics, explanation: good.result.explanation }]);
    } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  };
  const hasSync = !!sc?.params.some((p) => p.name === "synchronized");
  const cap = sim ? Number(sim.input.buffer ?? 0) : 0;
  const keys: string[] = pair ? Array.from(new Set<string>(pair.flatMap((p) => Object.keys(p.metrics)))) : [];

  return (
    <div className="max-w-[1500px] mx-auto">
      <PageHeader icon={<GitMerge size={26} />} title="Process Synchronization Simulator" subtitle="Deterministic threads, semaphores and locks: replay any interleaving." tag={sc?.title} />
      <div className="grid gap-4 xl:grid-cols-[340px_1fr_320px]">
        <Card title="Scenario & Parameters">
          <div className="space-y-4 text-sm">
            <label className="block"><span className="text-mute">Problem</span>
              <select className="w-full mt-1" value={sid} onChange={(e) => setSid(e.target.value)}>{catalog.map((c) => <option key={c.id} value={c.id}>{c.title}</option>)}</select></label>
            {sc && <p className="text-xs text-mute leading-relaxed">{sc.description}</p>}
            {sc?.params.map((p) => p.type === "bool"
              ? <label key={p.name} className="flex items-center gap-2"><input type="checkbox" className="!p-0" checked={!!vals[p.name]} onChange={(e) => setVals({ ...vals, [p.name]: e.target.checked })} />{p.label}</label>
              : p.type === "choice"
                ? <label key={p.name} className="block"><span className="text-mute">{p.label}</span><select className="w-full mt-1" value={String(vals[p.name] ?? "")} onChange={(e) => setVals({ ...vals, [p.name]: e.target.value })}>{p.options?.map((o) => <option key={o}>{o}</option>)}</select></label>
                : <label key={p.name} className="block"><span className="text-mute">{p.label} ({p.min}–{p.max})</span><input className="w-full mt-1" inputMode="numeric" value={String(vals[p.name] ?? "")} onChange={(e) => setVals({ ...vals, [p.name]: e.target.value })} /></label>)}
            <button onClick={run} disabled={busy || !sc} className="w-full flex items-center justify-center gap-2 bg-accent text-bg font-semibold rounded-md py-2.5">{busy ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}Start Simulation</button>
            {hasSync && <button onClick={runBoth} disabled={busy} className="w-full flex items-center justify-center gap-2 border border-accent/60 text-accent rounded-md py-2"><Scale size={16} />Compare with / without sync</button>}
            <PlayerBar player={player} length={sim?.steps.length ?? 0} onReset={() => { setSim(null); setPair(null); player.stop(); setErr(""); }} />
            {err && <p className="text-err border border-err/40 rounded-md p-2">{err}</p>}
            <p className="text-xs text-mute">Same parameters always give the same run, so you can reproduce a bug exactly. Raise the time slice to see a race disappear.</p>
          </div>
        </Card>

        <div className="space-y-4 min-w-0">
          <Card title="Live State">{cur ? <SyncState state={{ ...cur.state, capacity: cap }} /> : <p className="text-sm text-mute py-8 text-center">Start a simulation to see threads, semaphores and shared data.</p>}</Card>
          {cur && <Card title="What just happened"><p className={`text-sm rounded-md border p-3 ${cur.event === "violation" || cur.event === "deadlock" ? "border-err text-err" : cur.event === "blocked" ? "border-warn text-warn" : "border-line"}`}>{cur.explanation}</p></Card>}
          <Card title="Step-by-Step Execution">{sim ? <StepList steps={sim.steps} active={player.step} onSelect={player.jump} /> : <p className="text-sm text-mute">One scheduler tick per line.</p>}</Card>
        </div>

        <div className="space-y-4">
          <Card title="Outcome">{sim ? <><Kv items={Object.entries(sim.result.metrics as Record<string, number>).map(([k, v]) => [k.replace(/_/g, " "), String(v)])} /><p className={`text-sm mt-3 ${sim.result.deadlock || sim.result.violations ? "text-err" : "text-ok"}`}>{sim.result.explanation}</p></> : <p className="text-sm text-mute">No results yet.</p>}</Card>
          {pair && <Card title="With vs without synchronization">
            <table className="w-full text-xs text-center"><thead className="text-mute"><tr><th className="text-left">Metric</th>{pair.map((p) => <th key={p.label}>{p.label.split(" ")[0]}</th>)}</tr></thead><tbody>
              {keys.map((k) => <tr key={k} className="border-t border-line"><td className="text-left py-1">{k.replace(/_/g, " ")}</td>{pair.map((p) => <td key={p.label}>{String(p.metrics[k] ?? "—")}</td>)}</tr>)}</tbody></table>
            {pair.map((p) => <p key={p.label} className="text-xs mt-2"><b>{p.label}:</b> <span className="text-mute">{p.explanation}</span></p>)}</Card>}
        </div>
      </div>
    </div>
  );
}
