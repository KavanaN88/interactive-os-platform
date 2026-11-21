import { useState } from "react";
import { BarChart3, Loader2 } from "lucide-react";
import type { GCompare } from "../types";

interface Props {
  columns: [key: string, label: string, lowerBetter: boolean][];
  barKey: string; barLabel: string;
  options: { id: string; label: string }[]; defaults: string[];
  run: (ids: string[]) => Promise<GCompare>;
}

/** Generic side-by-side comparison. Every value shown comes from the backend response. */
export default function ComparePanel({ columns, barKey, barLabel, options, defaults, run }: Props) {
  const [picked, setPicked] = useState<string[]>(defaults);
  const [data, setData] = useState<GCompare | null>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const toggle = (id: string) => setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id]));
  const go = async () => {
    setErr(""); setBusy(true);
    try { setData(await run(picked)); } catch (e) { setData(null); setErr((e as Error).message); } finally { setBusy(false); }
  };
  const max = data ? Math.max(...data.runs.map((r) => r.metrics[barKey]), 0.0001) : 1;
  return (
    <div className="space-y-4">
      <p className="text-sm text-mute">All selected algorithms run on exactly the same input shown above.</p>
      <div className="flex flex-wrap gap-2">
        {options.map((o) => (
          <label key={o.id} className={`text-sm px-3 py-1.5 rounded-md border cursor-pointer ${picked.includes(o.id) ? "border-accent bg-accent/10 text-accent" : "border-line text-mute"}`}>
            <input type="checkbox" className="hidden" checked={picked.includes(o.id)} onChange={() => toggle(o.id)} />{o.label}
          </label>
        ))}
      </div>
      <button onClick={go} disabled={busy || picked.length < 2} className="inline-flex items-center gap-2 bg-accent text-bg font-semibold rounded-md px-4 py-2">
        {busy ? <Loader2 size={16} className="animate-spin" /> : <BarChart3 size={16} />}Compare {picked.length} selected
      </button>
      {err && <p className="text-sm text-err">{err}</p>}
      {data && (
        <>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-mute text-xs"><tr><th className="text-left py-1">Algorithm</th>{columns.map(([, l]) => <th key={l} className="font-medium">{l}</th>)}</tr></thead>
              <tbody>
                {data.runs.map((r) => (
                  <tr key={r.label} className="border-t border-line text-center">
                    <td className="text-left py-2">{r.label}</td>
                    {columns.map(([k]) => <td key={k} className={data.best_by_metric[k]?.includes(r.label) ? "text-ok font-semibold" : ""}>{r.metrics[k]}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="text-[11px] text-mute mt-1">Green = best for that metric. No green means a tie.</p>
          </div>
          <div className="space-y-2">
            <p className="text-sm text-mute">{barLabel}</p>
            {data.runs.map((r) => (
              <div key={r.label} className="flex items-center gap-3 text-xs">
                <span className="w-32 truncate text-mute">{r.label}</span>
                <div className="flex-1 bg-bg rounded h-4"><div className="h-4 rounded bg-accent" style={{ width: `${(r.metrics[barKey] / max) * 100}%` }} /></div>
                <span className="w-14 text-right font-mono">{r.metrics[barKey]}</span>
              </div>
            ))}
          </div>
          <ul className="list-disc pl-5 space-y-1 text-sm">{data.explanation.map((e, i) => <li key={i}>{e}</li>)}</ul>
        </>
      )}
    </div>
  );
}
