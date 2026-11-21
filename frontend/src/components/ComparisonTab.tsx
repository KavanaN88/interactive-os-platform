import { useState } from "react";
import { Loader2, BarChart3 } from "lucide-react";
import { api } from "../lib/api";
import type { AlgoInfo, CompareResponse, ProcessPayload } from "../types";

interface Props { algos: AlgoInfo[]; build: (ids: string[]) => { processes: ProcessPayload[]; configs: { algorithm: string; quantum: number | null; levels: (number | null)[] | null }[] } }

const COLS: [string, string, boolean][] = [
  ["avg_waiting_time", "Avg WT", true], ["avg_turnaround_time", "Avg TAT", true], ["avg_response_time", "Avg RT", true],
  ["cpu_utilization", "CPU %", false], ["throughput", "Throughput", false], ["context_switches", "Ctx switches", true],
];

export default function ComparisonTab({ algos, build }: Props) {
  const [picked, setPicked] = useState<string[]>(["fcfs", "sjf", "rr"]);
  const [data, setData] = useState<CompareResponse | null>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const toggle = (id: string) => setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id]));
  const run = async () => {
    setErr(""); setBusy(true);
    try { setData(await api.compare(build(picked))); } catch (e) { setData(null); setErr((e as Error).message); }
    finally { setBusy(false); }
  };
  const maxWt = data ? Math.max(...data.runs.map((r) => r.metrics.avg_waiting_time), 0.0001) : 1;

  return (
    <div className="space-y-4">
      <p className="text-sm text-mute">Every selected algorithm runs on the same processes entered in the Simulation tab.</p>
      <div className="flex flex-wrap gap-2">
        {algos.map((a) => (
          <label key={a.id} className={`text-sm px-3 py-1.5 rounded-md border cursor-pointer ${picked.includes(a.id) ? "border-accent bg-accent/10 text-accent" : "border-line text-mute"}`}>
            <input type="checkbox" className="hidden" checked={picked.includes(a.id)} onChange={() => toggle(a.id)} />{a.label}
          </label>
        ))}
      </div>
      <button onClick={run} disabled={busy || picked.length < 2} className="inline-flex items-center gap-2 bg-accent text-bg font-semibold rounded-md px-4 py-2">
        {busy ? <Loader2 size={16} className="animate-spin" /> : <BarChart3 size={16} />}Compare {picked.length} algorithms
      </button>
      {err && <p className="text-sm text-err">{err}</p>}
      {data && (
        <>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-mute text-xs"><tr><th className="text-left py-1">Algorithm</th>{COLS.map(([, h]) => <th key={h} className="font-medium">{h}</th>)}</tr></thead>
              <tbody>
                {data.runs.map((r) => (
                  <tr key={r.label} className="border-t border-line text-center">
                    <td className="text-left py-2">{r.label}</td>
                    {COLS.map(([k]) => {
                      const best = data.best_by_metric[k]?.includes(r.label);
                      return <td key={k} className={best ? "text-ok font-semibold" : ""}>{(r.metrics as unknown as Record<string, number>)[k]}</td>;
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="text-[11px] text-mute mt-1">Green = best for that metric. A metric with no green is a tie.</p>
          </div>
          <div className="space-y-2">
            <p className="text-sm text-mute">Average waiting time</p>
            {data.runs.map((r) => (
              <div key={r.label} className="flex items-center gap-3 text-xs">
                <span className="w-44 truncate text-mute">{r.label}</span>
                <div className="flex-1 bg-bg rounded h-4"><div className="h-4 rounded bg-accent" style={{ width: `${(r.metrics.avg_waiting_time / maxWt) * 100}%` }} /></div>
                <span className="w-12 text-right font-mono">{r.metrics.avg_waiting_time}</span>
              </div>
            ))}
          </div>
          <ul className="list-disc pl-5 space-y-1 text-sm text-ink/90">{data.explanation.map((e, i) => <li key={i}>{e}</li>)}</ul>
        </>
      )}
    </div>
  );
}
