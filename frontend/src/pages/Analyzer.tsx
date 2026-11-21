import { useEffect, useState } from "react";
import { BarChart3, Download, Loader2, Save, Trash2 } from "lucide-react";
import Card from "../components/Card";
import PageHeader from "../components/PageHeader";
import { get, post } from "../lib/api";
import { parseFsOps, parseIntList, parseOps, toInt } from "../lib/parse";

interface Cat { module: string; label: string; algorithms: { id: string; label: string }[]; defaults: string[]; metrics: [string, string, boolean][] }
interface Result { module: string; label: string; runs: { label: string; metrics: Record<string, number> }[]; best_by_metric: Record<string, string[]>; explanation: string[]; recommendations: string[] }
interface Saved { id: string; time: string; module: string; algorithms: string[]; workload: Record<string, unknown>; result: Result }
const KEY = "oslab.analyzer.saved";
const load = (): Saved[] => { try { return JSON.parse(localStorage.getItem(KEY) ?? "[]"); } catch { return []; } };

const D = {
  cpu: { procs: "P1 0 8\nP2 1 4\nP3 2 1\nP4 3 3", quantum: "2" },
  paging: { refs: "7,0,1,2,0,3,0,4,2,3,0,3,2,1,2,0,1,7,0,1", frames: "3" },
  disk: { requests: "98,183,37,122,14,124,65,67", head: "53", max: "199", dir: "up" },
  memory: { blocks: "100,500,200,300,600", ops: "alloc P1 212\nalloc P2 417\nalloc P3 112\nalloc P4 426", mode: "variable" },
  fs: { total: "16", bs: "1", ops: "create /a 3\ncreate /b 2\ndelete /a\ncreate /c 4\ncreate /d 8" },
  vm: { page: "1024", virt: "8192", phys: "2048", tlb: "2", addrs: "0, 1024, 0, 2048, 1024, 3000, 0", tlbPol: "lru" },
};

export default function Analyzer() {
  const [cat, setCat] = useState<Cat[]>([]);
  const [module, setModule] = useState("cpu");
  const [picked, setPicked] = useState<string[]>([]);
  const [f, setF] = useState(D);
  const [res, setRes] = useState<Result | null>(null);
  const [metric, setMetric] = useState("");
  const [saved, setSaved] = useState<Saved[]>(load);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const c = cat.find((x) => x.module === module);

  useEffect(() => { get<Cat[]>("/analyzer/catalog").then((x) => { setCat(x); setPicked(x[0].defaults); setMetric(x[0].metrics[0][0]); }).catch((e: Error) => setErr(e.message)); }, []);
  const pickModule = (m: string) => { const x = cat.find((k) => k.module === m)!; setModule(m); setPicked(x.defaults); setMetric(x.metrics[0][0]); setRes(null); setErr(""); };
  const set = <K extends keyof typeof D>(k: K, patch: Partial<(typeof D)[K]>) => setF({ ...f, [k]: { ...f[k], ...patch } });

  const workload = (): Record<string, unknown> => {
    if (module === "cpu") return { quantum: toInt(f.cpu.quantum, "Quantum"), processes: f.cpu.procs.split("\n").map((l) => l.trim()).filter(Boolean).map((l, i) => {
      const [pid, a, b, p] = l.split(/\s+/);
      if (!pid || a === undefined || b === undefined) throw new Error(`Line ${i + 1}: write "PID arrival burst [priority]"`);
      return { pid, arrival: toInt(a, `Line ${i + 1} arrival`), burst: toInt(b, `Line ${i + 1} burst`), priority: p ? toInt(p, `Line ${i + 1} priority`) : 0 }; }) };
    if (module === "paging") return { refs: parseIntList(f.paging.refs, "Reference string"), frames: toInt(f.paging.frames, "Frames") };
    if (module === "disk") return { requests: parseIntList(f.disk.requests, "Requests"), head: toInt(f.disk.head, "Head"), max_cylinder: toInt(f.disk.max, "Max cylinder"), direction: f.disk.dir };
    if (module === "memory") return { blocks: parseIntList(f.memory.blocks, "Blocks"), ops: parseOps(f.memory.ops), mode: f.memory.mode };
    if (module === "fs") return { total_blocks: toInt(f.fs.total, "Disk blocks"), block_size_kb: toInt(f.fs.bs, "Block size"), ops: parseFsOps(f.fs.ops) };
    return { page_size: toInt(f.vm.page, "Page size"), virtual_size: toInt(f.vm.virt, "Virtual"), physical_size: toInt(f.vm.phys, "Physical"), tlb_size: toInt(f.vm.tlb, "TLB"), tlb_policy: f.vm.tlbPol, addresses: parseIntList(f.vm.addrs, "Addresses") };
  };
  const payload = () => ({ module, workload: workload(), algorithms: picked });
  const run = async () => { setErr(""); setBusy(true); try { setRes(await post<Result>("/analyzer/compare", payload())); } catch (e) { setRes(null); setErr((e as Error).message); } finally { setBusy(false); } };
  const download = async () => {
    try {
      const r = await post<{ filename: string; markdown: string }>("/analyzer/report", payload());
      const url = URL.createObjectURL(new Blob([r.markdown], { type: "text/markdown" }));
      const a = document.createElement("a"); a.href = url; a.download = r.filename; a.click(); URL.revokeObjectURL(url);
    } catch (e) { setErr((e as Error).message); }
  };
  const save = () => {
    if (!res) return;
    const entry: Saved = { id: String(Date.now()), time: new Date().toLocaleString(), module, algorithms: picked, workload: workload(), result: res };
    const next = [entry, ...saved].slice(0, 30);
    setSaved(next); try { localStorage.setItem(KEY, JSON.stringify(next)); } catch { setErr("Could not save in this browser (storage is full or disabled)."); }
  };
  const del = (id: string) => { const next = saved.filter((s) => s.id !== id); setSaved(next); localStorage.setItem(KEY, JSON.stringify(next)); };
  const max = res ? Math.max(...res.runs.map((r) => r.metrics[metric]), 0.0001) : 1;
  const T = (k: "cpu" | "paging" | "disk" | "memory" | "fs" | "vm", name: string, label: string) => (
    <label className="block"><span className="text-mute">{label}</span><input className="w-full mt-1 font-mono" value={(f[k] as Record<string, string>)[name]} onChange={(e) => set(k, { [name]: e.target.value } as never)} /></label>);

  return (
    <div className="max-w-[1500px] mx-auto">
      <PageHeader icon={<BarChart3 size={26} />} title="OS Performance Analyzer & Compare" subtitle="Run several algorithms on one identical workload. Every number is computed by the backend engines." tag={c?.label} />
      <div className="grid gap-4 xl:grid-cols-[360px_1fr]">
        <Card title="Workload & Algorithms">
          <div className="space-y-4 text-sm">
            <label className="block"><span className="text-mute">Category</span><select className="w-full mt-1" value={module} onChange={(e) => pickModule(e.target.value)}>{cat.map((x) => <option key={x.module} value={x.module}>{x.label}</option>)}</select></label>
            {module === "cpu" && <><label className="block"><span className="text-mute">Processes: PID arrival burst [priority]</span><textarea className="w-full mt-1 font-mono bg-bg border border-line rounded-md p-2 outline-none focus:border-accent" rows={5} value={f.cpu.procs} onChange={(e) => set("cpu", { procs: e.target.value })} /></label>{T("cpu", "quantum", "Round Robin quantum")}</>}
            {module === "paging" && <>{T("paging", "refs", "Reference string")}{T("paging", "frames", "Frames")}</>}
            {module === "disk" && <>{T("disk", "requests", "Request queue")}<div className="grid grid-cols-2 gap-3">{T("disk", "head", "Head")}{T("disk", "max", "Max cylinder")}</div></>}
            {module === "memory" && <>{T("memory", "blocks", "Memory blocks (KB)")}<label className="block"><span className="text-mute">Operations</span><textarea className="w-full mt-1 font-mono bg-bg border border-line rounded-md p-2 outline-none focus:border-accent" rows={5} value={f.memory.ops} onChange={(e) => set("memory", { ops: e.target.value })} /></label>
              <label className="block"><span className="text-mute">Partitioning</span><select className="w-full mt-1" value={f.memory.mode} onChange={(e) => set("memory", { mode: e.target.value })}><option value="variable">Variable</option><option value="fixed">Fixed</option></select></label></>}
            {module === "fs" && <><div className="grid grid-cols-2 gap-3">{T("fs", "total", "Disk blocks")}{T("fs", "bs", "Block size KB")}</div><label className="block"><span className="text-mute">Operations</span><textarea className="w-full mt-1 font-mono bg-bg border border-line rounded-md p-2 outline-none focus:border-accent" rows={6} value={f.fs.ops} onChange={(e) => set("fs", { ops: e.target.value })} /></label></>}
            {module === "vm" && <><div className="grid grid-cols-2 gap-3">{T("vm", "page", "Page size")}{T("vm", "tlb", "TLB entries")}{T("vm", "virt", "Virtual bytes")}{T("vm", "phys", "Physical bytes")}</div>{T("vm", "addrs", "Addresses")}</>}
            <div><p className="text-mute mb-1">Algorithms to compare</p><div className="flex flex-wrap gap-2">{c?.algorithms.map((a) => (
              <label key={a.id} className={`px-3 py-1.5 rounded-md border cursor-pointer ${picked.includes(a.id) ? "border-accent bg-accent/10 text-accent" : "border-line text-mute"}`}>
                <input type="checkbox" className="hidden" checked={picked.includes(a.id)} onChange={() => setPicked(picked.includes(a.id) ? picked.filter((x) => x !== a.id) : [...picked, a.id])} />{a.label}</label>))}</div></div>
            <button onClick={run} disabled={busy || picked.length < 2} className="w-full flex items-center justify-center gap-2 bg-accent text-bg font-semibold rounded-md py-2.5">{busy ? <Loader2 size={16} className="animate-spin" /> : <BarChart3 size={16} />}Compare {picked.length} algorithms</button>
            {err && <p className="text-err border border-err/40 rounded-md p-2">{err}</p>}
          </div>
        </Card>

        <div className="space-y-4 min-w-0">
          {!res && <Card title="Results"><p className="text-sm text-mute py-10 text-center">Choose a category, edit the workload if you like, and press Compare.</p></Card>}
          {res && c && <>
            <Card title={`Results: ${res.label}`}>
              <div className="overflow-x-auto"><table className="w-full text-sm"><thead className="text-mute text-xs"><tr><th className="text-left py-1">Algorithm</th>{c.metrics.map(([k, l]) => <th key={k} className="font-medium">{l}</th>)}</tr></thead><tbody>
                {res.runs.map((r) => <tr key={r.label} className="border-t border-line text-center"><td className="text-left py-2">{r.label}</td>{c.metrics.map(([k]) => <td key={k} className={res.best_by_metric[k]?.includes(r.label) ? "text-ok font-semibold" : ""}>{r.metrics[k]}</td>)}</tr>)}</tbody></table></div>
              <p className="text-[11px] text-mute mt-1">Green = best for that metric; no green = tie.</p>
              <div className="flex flex-wrap gap-2 mt-4"><button onClick={download} className="inline-flex items-center gap-1.5 border border-accent/60 text-accent rounded-md px-3 py-1.5 hover:bg-accent/10"><Download size={15} />Download report (.md)</button>
                <button onClick={save} className="inline-flex items-center gap-1.5 border border-line rounded-md px-3 py-1.5 hover:bg-line/40"><Save size={15} />Save in this browser</button></div>
            </Card>
            <Card title="Chart">
              <label className="text-sm text-mute">Metric <select className="ml-2" value={metric} onChange={(e) => setMetric(e.target.value)}>{c.metrics.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></label>
              <div className="space-y-2 mt-3">{res.runs.map((r) => <div key={r.label} className="flex items-center gap-3 text-xs"><span className="w-40 truncate text-mute">{r.label}</span>
                <div className="flex-1 bg-bg rounded h-5"><div className={`h-5 rounded ${res.best_by_metric[metric]?.includes(r.label) ? "bg-ok" : "bg-accent"}`} style={{ width: `${(r.metrics[metric] / max) * 100}%` }} /></div><span className="w-16 text-right font-mono">{r.metrics[metric]}</span></div>)}</div>
            </Card>
            <Card title="Why the results differ"><ul className="list-disc pl-5 space-y-1 text-sm">{res.explanation.map((e, i) => <li key={i}>{e}</li>)}</ul></Card>
            <Card title="Recommendations for this workload"><ul className="list-disc pl-5 space-y-1.5 text-sm">{res.recommendations.map((e, i) => <li key={i}>{e}</li>)}</ul></Card></>}
          <Card title={`Saved comparisons (${saved.length})`}>
            {saved.length === 0 ? <p className="text-sm text-mute">Nothing saved yet. Saved comparisons stay in this browser only.</p> :
              <ul className="space-y-2 text-sm">{saved.map((s) => <li key={s.id} className="flex items-center gap-3 border border-line rounded-md px-3 py-2"><div className="flex-1 min-w-0"><b>{s.result.label}</b> <span className="text-mute">· {s.time} · {s.algorithms.length} algorithms</span></div>
                <button className="text-accent text-xs underline" onClick={() => { setModule(s.module); setPicked(s.algorithms); setRes(s.result); setMetric(cat.find((x) => x.module === s.module)?.metrics[0][0] ?? ""); }}>View</button>
                <button className="text-mute hover:text-err" onClick={() => del(s.id)} aria-label="Delete"><Trash2 size={15} /></button></li>)}</ul>}
          </Card>
        </div>
      </div>
    </div>
  );
}
