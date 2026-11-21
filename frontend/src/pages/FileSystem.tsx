import { useState } from "react";
import { FolderTree, Loader2, Play } from "lucide-react";
import Card from "../components/Card";
import Kv from "../components/Kv";
import PageHeader from "../components/PageHeader";
import PlayerBar from "../components/PlayerBar";
import StepList from "../components/StepList";
import ComparePanel from "../components/ComparePanel";
import { DirTree, DiskMap } from "../components/visuals2";
import { usePlayer } from "../hooks/usePlayer";
import { post } from "../lib/api";
import { parseFsOps, toInt } from "../lib/parse";
import type { GCompare, GSim } from "../types";

const DEMO = "mkdir /docs\ncreate /docs/report.txt 3\ncreate /docs/data.csv 2\ncreate /notes.txt 4\nread /docs/report.txt\nappend /notes.txt 2\ndelete /docs/data.csv\ncreate /big.bin 5";
const FRAG = "create /a 3\ncreate /b 2\ndelete /a\ncreate /c 4\ncreate /d 8   # needs 8 blocks: only contiguous fails";
const METHODS = [{ id: "contiguous", label: "Contiguous" }, { id: "linked", label: "Linked" }, { id: "indexed", label: "Indexed" }];
const HELP: Record<string, string> = {
  contiguous: "Each file occupies one run of consecutive blocks. Direct access is fast, but a file needs a long enough free run.",
  linked: "Each block holds a pointer to the next block, so any free block can be used. Random access must follow the chain.",
  indexed: "An index block lists every data block of the file: direct access with scattered blocks, at the cost of one index block per file.",
};

export default function FileSystem() {
  const [method, setMethod] = useState("contiguous");
  const [total, setTotal] = useState("16");
  const [bs, setBs] = useState("1");
  const [opsText, setOpsText] = useState(DEMO);
  const [sim, setSim] = useState<GSim | null>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const player = usePlayer(sim?.steps.length ?? 0);
  const cur = sim?.steps[player.step];
  const input = () => ({ total_blocks: toInt(total, "Disk blocks"), block_size_kb: toInt(bs, "Block size"), ops: parseFsOps(opsText) });
  const start = async () => {
    setErr(""); setBusy(true);
    try { setSim(await post<GSim>("/filesystem/simulate", { ...input(), method })); player.load(); } catch (e) { setErr((e as Error).message); setSim(null); } finally { setBusy(false); }
  };
  const order = sim ? (sim.input.ops as { path: string }[]).map((o) => o.path) : [];
  const s = cur?.state;

  return (
    <div className="max-w-[1500px] mx-auto">
      <PageHeader icon={<FolderTree size={26} />} title="File System Simulator" subtitle="Virtual disk only: nothing here touches your real files." tag={`Method: ${METHODS.find((m) => m.id === method)?.label}`} />
      <div className="grid gap-4 xl:grid-cols-[340px_1fr_330px]">
        <Card title="Disk & Operations">
          <div className="space-y-4 text-sm">
            <label className="block"><span className="text-mute">Allocation method</span><select className="w-full mt-1" value={method} onChange={(e) => setMethod(e.target.value)}>{METHODS.map((m) => <option key={m.id} value={m.id}>{m.label} allocation</option>)}</select></label>
            <p className="text-xs text-mute leading-relaxed">{HELP[method]}</p>
            <div className="grid grid-cols-2 gap-3">
              <label className="block"><span className="text-mute">Disk blocks (4–512)</span><input className="w-full mt-1" value={total} onChange={(e) => setTotal(e.target.value)} /></label>
              <label className="block"><span className="text-mute">Block size (KB)</span><input className="w-full mt-1" value={bs} onChange={(e) => setBs(e.target.value)} /></label>
            </div>
            <label className="block"><span className="text-mute">Operations (one per line)</span>
              <textarea className="w-full mt-1 font-mono bg-bg border border-line rounded-md p-2 outline-none focus:border-accent" rows={9} value={opsText} onChange={(e) => setOpsText(e.target.value)} />
              <span className="text-[11px] text-mute">mkdir /p · create /p KB · append /p KB · read /p · delete /p</span></label>
            <div className="flex gap-2 text-xs"><button className="border border-line rounded px-2 py-1 hover:bg-line/40" onClick={() => { setOpsText(DEMO); setTotal("16"); }}>Basic demo</button>
              <button className="border border-line rounded px-2 py-1 hover:bg-line/40" onClick={() => { setOpsText(FRAG); setTotal("16"); }}>Fragmentation demo</button></div>
            <button onClick={start} disabled={busy} className="w-full flex items-center justify-center gap-2 bg-accent text-bg font-semibold rounded-md py-2.5">{busy ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}Start Simulation</button>
            <PlayerBar player={player} length={sim?.steps.length ?? 0} onReset={() => { setSim(null); player.stop(); setErr(""); }} />
            {err && <p className="text-err border border-err/40 rounded-md p-2">{err}</p>}
          </div>
        </Card>

        <div className="space-y-4 min-w-0">
          <Card title="Virtual Disk Explorer">{s ? <DiskMap owners={s.owners} roles={s.roles} order={order} highlight={s.disk_requests} /> : <p className="text-sm text-mute py-8 text-center">Start a simulation to see which block belongs to which file.</p>}
            {s?.disk_requests?.length > 0 && <p className="text-xs mt-2 text-mute">Disk requests from this step (feed them to Disk Scheduling): <span className="font-mono text-ink">{s.disk_requests.join(", ")}</span></p>}
            {s?.next && method === "linked" && Object.keys(s.next).length > 0 && <p className="text-xs mt-1 text-mute">Pointers: <span className="font-mono text-ink">{Object.entries(s.next as Record<string, number | null>).map(([k, v]) => `${k}→${v ?? "∅"}`).join("  ")}</span></p>}</Card>
          {s && <div className="grid md:grid-cols-2 gap-4">
            <Card title="Directory Tree"><DirTree node={s.tree} /></Card>
            <Card title="Files"><table className="w-full text-xs text-center"><thead className="text-mute"><tr><th className="text-left">File</th><th>KB</th><th>Blocks</th><th>Frags</th></tr></thead><tbody>
              {(s.files_detail as { path: string; size_kb: number; blocks: number[]; index_block: number | null; fragments: number }[]).map((f) => <tr key={f.path} className="border-t border-line"><td className="text-left py-1">{f.path}</td><td>{f.size_kb}</td><td className="font-mono">{f.index_block !== null ? `idx ${f.index_block}: ` : ""}{f.blocks.join(",")}</td><td>{f.fragments}</td></tr>)}</tbody></table></Card></div>}
          <Card title="Step-by-Step Explanation">{sim ? <StepList steps={sim.steps} active={player.step} onSelect={player.jump} /> : <p className="text-sm text-mute">How each operation uses the disk appears here.</p>}</Card>
        </div>

        <div className="space-y-4">
          <Card title="Disk Statistics">{s ? <Kv items={[["Total blocks", s.total_blocks], ["Used", s.used_blocks], ["Free", s.free_blocks], ["Utilization", `${s.utilization_pct}%`], ["Index blocks", s.index_blocks], ["Largest free run", s.largest_free_run],
            ["External fragmentation", `${s.external_fragmentation_pct}%`], ["Avg fragments/file", s.avg_fragments_per_file]]} /> : <p className="text-sm text-mute">No results yet.</p>}</Card>
          {sim && player.step === sim.steps.length - 1 && <Card title="Final Outcome"><Kv items={[["Failed operations", sim.result.metrics.failed_operations]]} /></Card>}
        </div>
      </div>
      <Card title="Allocation Method Comparison" className="mt-4">
        <ComparePanel columns={[["failed_operations", "Failed ops", true], ["utilization_pct", "Utilization %", false], ["index_blocks", "Index blocks", true], ["external_fragmentation_pct", "External frag %", true], ["avg_fragments_per_file", "Frags/file", true]]}
          barKey="utilization_pct" barLabel="Disk utilization %" options={METHODS} defaults={["contiguous", "linked", "indexed"]} run={(ids) => post<GCompare>("/filesystem/compare", { ...input(), methods: ids })} />
      </Card>
    </div>
  );
}
