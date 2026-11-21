import { useState } from "react";
import { ShieldAlert, Loader2 } from "lucide-react";
import Card from "../components/Card";
import PageHeader from "../components/PageHeader";
import PlayerBar from "../components/PlayerBar";
import StepList from "../components/StepList";
import { MatrixTable, RagGraph } from "../components/visuals";
import { usePlayer } from "../hooks/usePlayer";
import { post } from "../lib/api";
import { toInt } from "../lib/parse";
import type { GSim } from "../types";

type Grid = string[][];
const g = (m: number[][]): Grid => m.map((r) => r.map(String));
const v = (a: number[]): string[] => a.map(String);

interface Preset { name: string; note: string; available: number[]; allocation: number[][]; maximum: number[][]; request: number[][] }
const addM = (a: number[][], b: number[][]) => a.map((r, i) => r.map((x, j) => x + b[i][j]));
const DL_AL = [[0, 1, 0], [2, 0, 0], [3, 0, 3], [2, 1, 1], [0, 0, 2]];
const DL_RQ = [[0, 0, 0], [2, 0, 2], [0, 0, 1], [1, 0, 0], [0, 0, 2]];
const PRESETS: Preset[] = [
  { name: "Safe state (textbook)", note: "Five processes, three resource types. A safe sequence exists.", available: [3, 3, 2],
    allocation: [[0, 1, 0], [2, 0, 0], [3, 0, 2], [2, 1, 1], [0, 0, 2]], maximum: [[7, 5, 3], [3, 2, 2], [9, 0, 2], [2, 2, 2], [4, 3, 3]], request: [[0, 0, 0], [0, 0, 0], [0, 0, 0], [0, 0, 0], [0, 0, 0]] },
  { name: "Unsafe but not deadlocked", note: "No safe sequence, yet nobody is waiting yet: unsafe ≠ deadlock.", available: [0],
    allocation: [[1], [1]], maximum: [[2], [2]], request: [[0], [0]] },
  { name: "Circular wait (2 processes)", note: "P0 holds R0 and wants R1; P1 holds R1 and wants R0. Classic deadlock.", available: [0, 0],
    allocation: [[1, 0], [0, 1]], maximum: [[1, 1], [1, 1]], request: [[0, 1], [1, 0]] },
  { name: "Deadlock among 4 of 5", note: "Textbook detection example with P2 requesting one more C.", available: [0, 0, 0],
    allocation: DL_AL, maximum: addM(DL_AL, DL_RQ), request: DL_RQ },
];

type Mode = "safety" | "detect" | "recover";
interface GraphRes { nodes: { id: string; type: string; instances?: number }[]; edges: { from: string; to: string; kind: string; count: number }[]; cycle: string[]; explanation: string }

export default function DeadlockManagement() {
  const [av, setAv] = useState<string[]>(v(PRESETS[0].available));
  const [al, setAl] = useState<Grid>(g(PRESETS[0].allocation));
  const [mx, setMx] = useState<Grid>(g(PRESETS[0].maximum));
  const [rq, setRq] = useState<Grid>(g(PRESETS[0].request));
  const [presetNote, setPresetNote] = useState(PRESETS[0].note);
  const [mode, setMode] = useState<Mode>("safety");
  const [sim, setSim] = useState<GSim | null>(null);
  const [graph, setGraph] = useState<GraphRes | null>(null);
  const [reqPid, setReqPid] = useState("1");
  const [reqVec, setReqVec] = useState("1,0,2");
  const [reqOut, setReqOut] = useState<{ granted: boolean; reason: string; available?: number[]; allocation?: number[][] } | null>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const n = al.length, m = av.length;
  const player = usePlayer(sim?.steps.length ?? 0);
  const cur = sim?.steps[player.step];

  const num = (grid: Grid, label: string) => grid.map((r, i) => r.map((c, j) => toInt(c, `${label} P${i}/R${j}`)));
  const vec = (a: string[], label: string) => a.map((c, j) => toInt(c, `${label} R${j}`));
  const run = async (f: () => Promise<void>) => { setErr(""); setBusy(true); try { await f(); } catch (e) { setErr((e as Error).message); } finally { setBusy(false); } };

  const loadPreset = (p: Preset) => { setAv(v(p.available)); setAl(g(p.allocation)); setMx(g(p.maximum)); setRq(g(p.request)); setPresetNote(p.note); setSim(null); setGraph(null); setReqOut(null); player.stop(); setErr(""); };
  const resize = (dn: number, dm: number) => {
    const nn = Math.min(20, Math.max(1, n + dn)), mm = Math.min(10, Math.max(1, m + dm));
    const fit = (grid: Grid) => Array.from({ length: nn }, (_, i) => Array.from({ length: mm }, (_, j) => grid[i]?.[j] ?? "0"));
    setAv(Array.from({ length: mm }, (_, j) => av[j] ?? "0")); setAl(fit(al)); setMx(fit(mx)); setRq(fit(rq)); setSim(null); setGraph(null);
  };

  const doSafety = () => run(async () => { setSim(await post<GSim>("/deadlock/safety", { available: vec(av, "Available"), allocation: num(al, "Allocation"), maximum: num(mx, "Maximum") })); setMode("safety"); player.load(); });
  const doDetect = (kind: "detect" | "recover") => run(async () => {
    const body = { available: vec(av, "Available"), allocation: num(al, "Allocation"), request: num(rq, "Request") };
    setSim(kind === "detect" ? await post<GSim>("/deadlock/detect", body) : await post<GSim>("/deadlock/recover", body)); setMode(kind); player.load();
  });
  const doGraph = () => run(async () => { setGraph(await post<GraphRes>("/deadlock/graph", { available: vec(av, "Available"), allocation: num(al, "Allocation"), request: num(rq, "Request") })); });
  const doRequest = () => run(async () => {
    const body = { available: vec(av, "Available"), allocation: num(al, "Allocation"), maximum: num(mx, "Maximum"), pid: toInt(reqPid, "Process"), request: reqVec.split(/[,\s]+/).filter(Boolean).map((x) => toInt(x, "Request")) };
    setReqOut(await post<NonNullable<typeof reqOut>>("/deadlock/request", body));
  });
  const applyGranted = () => { if (reqOut?.granted && reqOut.available && reqOut.allocation) { setAv(v(reqOut.available)); setAl(g(reqOut.allocation)); setReqOut(null); setSim(null); } };

  const setCell = (setter: (x: Grid) => void, grid: Grid, i: number, j: number, val: string) => setter(grid.map((r, a) => r.map((c, b) => (a === i && b === j ? val : c))));
  const matrixInput = (title: string, grid: Grid, setter: (x: Grid) => void) => (
    <div><p className="text-xs text-mute mb-1">{title}</p>
      <table className="text-sm"><thead className="text-mute text-xs"><tr><th />{Array.from({ length: m }, (_, j) => <th key={j} className="font-normal">R{j}</th>)}</tr></thead>
        <tbody>{grid.map((r, i) => <tr key={i}><td className="text-mute text-xs pr-2">P{i}</td>{r.map((c, j) => (
          <td key={j}><input className="w-12 text-center !px-1" inputMode="numeric" value={c} onChange={(e) => setCell(setter, grid, i, j, e.target.value)} aria-label={`${title} P${i} R${j}`} /></td>))}</tr>)}</tbody></table></div>
  );

  const finished = cur?.state.finished as string[] | undefined;
  return (
    <div className="max-w-[1500px] mx-auto">
      <PageHeader icon={<ShieldAlert size={26} />} title="Deadlock Management Simulator" subtitle="Banker's algorithm, request testing, detection, recovery and the resource allocation graph." tag="Deadlock Laboratory" />
      <div className="grid gap-4 xl:grid-cols-[430px_1fr_330px]">
        <Card title="System State">
          <div className="space-y-4 text-sm">
            <div><p className="text-mute text-xs mb-1">Deadlock Laboratory presets</p>
              <div className="flex flex-wrap gap-2">{PRESETS.map((p) => <button key={p.name} className="border border-line rounded px-2 py-1 text-xs hover:bg-line/40" onClick={() => loadPreset(p)}>{p.name}</button>)}</div>
              <p className="text-xs text-mute mt-2">{presetNote}</p></div>
            <div className="flex gap-2 text-xs items-center text-mute">Processes {n}
              <button className="border border-line rounded px-2" onClick={() => resize(-1, 0)}>−</button><button className="border border-line rounded px-2" onClick={() => resize(1, 0)}>+</button>
              <span className="ml-3">Resources {m}</span>
              <button className="border border-line rounded px-2" onClick={() => resize(0, -1)}>−</button><button className="border border-line rounded px-2" onClick={() => resize(0, 1)}>+</button></div>
            <div><p className="text-xs text-mute mb-1">Available</p>
              <div className="flex gap-1">{av.map((c, j) => <input key={j} className="w-12 text-center !px-1" inputMode="numeric" value={c} onChange={(e) => setAv(av.map((x, k) => (k === j ? e.target.value : x)))} aria-label={`Available R${j}`} />)}</div></div>
            {matrixInput("Allocation (held now)", al, setAl)}
            {matrixInput("Maximum (Banker's algorithm)", mx, setMx)}
            {matrixInput("Request (detection / graph)", rq, setRq)}
            <div className="grid grid-cols-2 gap-2">
              <button disabled={busy} onClick={doSafety} className="bg-accent text-bg font-semibold rounded-md py-2">Run safety check</button>
              <button disabled={busy} onClick={() => doDetect("detect")} className="border border-accent/60 text-accent rounded-md py-2">Detect deadlock</button>
              <button disabled={busy} onClick={() => doDetect("recover")} className="border border-line rounded-md py-2 hover:bg-line/40">Recover</button>
              <button disabled={busy} onClick={doGraph} className="border border-line rounded-md py-2 hover:bg-line/40">Draw graph</button>
            </div>
            {busy && <p className="flex items-center gap-2 text-mute"><Loader2 size={14} className="animate-spin" />Working…</p>}
            {err && <p className="text-err border border-err/40 rounded-md p-2">{err}</p>}
          </div>
        </Card>

        <div className="space-y-4 min-w-0">
          <Card title={mode === "safety" ? "Safety Algorithm" : mode === "detect" ? "Deadlock Detection" : "Deadlock Recovery"}>
            {sim && cur ? (
              <div className="space-y-4">
                <PlayerBar player={player} length={sim.steps.length} onReset={() => { setSim(null); player.stop(); }} />
                <div className="grid sm:grid-cols-2 gap-3 text-sm">
                  {cur.state.work && <div className="border border-line rounded-lg p-3"><p className="text-mute text-xs mb-1">Work vector</p><p className="font-mono text-lg">[{(cur.state.work as number[]).join(", ")}]</p></div>}
                  {cur.state.available && <div className="border border-line rounded-lg p-3"><p className="text-mute text-xs mb-1">Available now</p><p className="font-mono text-lg">[{(cur.state.available as number[]).join(", ")}]</p></div>}
                  {cur.state.sequence && <div className="border border-line rounded-lg p-3"><p className="text-mute text-xs mb-1">{mode === "safety" ? "Safe sequence so far" : "Completion order so far"}</p>
                    <p className="font-mono">{(cur.state.sequence as string[]).join(" → ") || "—"}</p></div>}
                  {cur.state.terminated && <div className="border border-line rounded-lg p-3"><p className="text-mute text-xs mb-1">Terminated</p><p className="font-mono">{(cur.state.terminated as string[]).join(", ") || "none"}</p></div>}
                </div>
                <p className={`text-sm rounded-md border p-3 ${["unsafe", "deadlock"].includes(cur.event) ? "border-err text-err" : ["safe", "recovered"].includes(cur.event) ? "border-ok text-ok" : "border-line"}`}>{cur.explanation}</p>
                <StepList steps={sim.steps} active={player.step} onSelect={player.jump} />
              </div>
            ) : <p className="text-sm text-mute py-8 text-center">Choose an action on the left. Each decision is explained step by step.</p>}
          </Card>
          {mode === "safety" && sim && (
            <Card title="Matrices">
              <div className="flex flex-wrap gap-6">
                <MatrixTable title="Allocation" rows={sim.input.allocation as number[][]} mark={(i) => (finished?.includes(`P${i}`) ? "text-ok" : "")} />
                <MatrixTable title="Maximum" rows={sim.input.maximum as number[][]} />
                <MatrixTable title="Need = Maximum − Allocation" rows={sim.result.need as number[][]} mark={(i) => (finished?.includes(`P${i}`) ? "text-ok" : "")} />
              </div>
              <p className="text-[11px] text-mute mt-2">Green rows have finished and returned their resources.</p>
            </Card>)}
          {graph && (
            <Card title="Resource Allocation Graph">
              <RagGraph nodes={graph.nodes} edges={graph.edges} cycle={graph.cycle} />
              <p className="text-[11px] text-mute mt-1">Solid arrow R→P = allocated · dashed P→R = requesting · red = cycle</p>
              <p className={`text-sm mt-2 ${graph.cycle.length ? "text-err" : "text-ok"}`}>{graph.explanation}</p>
            </Card>)}
        </div>

        <div className="space-y-4">
          <Card title="Test a Resource Request">
            <div className="space-y-3 text-sm">
              <p className="text-mute text-xs">Banker's algorithm grants a request only if the resulting state is safe.</p>
              <div className="grid grid-cols-[80px_1fr] gap-2 items-center"><span className="text-mute">Process</span><input value={reqPid} onChange={(e) => setReqPid(e.target.value)} inputMode="numeric" />
                <span className="text-mute">Request</span><input className="font-mono" value={reqVec} onChange={(e) => setReqVec(e.target.value)} /></div>
              <button disabled={busy} onClick={doRequest} className="w-full border border-accent/60 text-accent rounded-md py-2">Check request</button>
              {reqOut && <div className={`rounded-md border p-3 ${reqOut.granted ? "border-ok text-ok" : "border-err text-err"}`}><p>{reqOut.reason}</p>
                {reqOut.granted && <button onClick={applyGranted} className="mt-2 text-xs underline">Apply this allocation to the matrices</button>}</div>}
            </div>
          </Card>
          <Card title="Remember"><ul className="text-xs text-mute space-y-2 list-disc pl-4">
            <li>Deadlock needs mutual exclusion, hold &amp; wait, no preemption and circular wait.</li>
            <li>An unsafe state is a warning, not proof that deadlock has happened.</li>
            <li>Recovery here terminates the deadlocked process holding the most resources.</li></ul></Card>
        </div>
      </div>
    </div>
  );
}
