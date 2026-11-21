import { Play, Pause, RotateCcw, SkipBack, SkipForward, Plus, Trash2, Loader2 } from "lucide-react";
import type { AlgoInfo, ProcessRow } from "../types";

interface Props {
  algos: AlgoInfo[]; algo?: AlgoInfo; algoId: string; setAlgoId: (v: string) => void;
  quantum: string; setQuantum: (v: string) => void; levels: string; setLevels: (v: string) => void;
  rows: ProcessRow[]; setRows: (r: ProcessRow[]) => void;
  hasSim: boolean; playing: boolean; busy: boolean; canPrev: boolean; canNext: boolean;
  speed: number; setSpeed: (v: number) => void;
  onStart: () => void; onTogglePlay: () => void; onPrev: () => void; onNext: () => void; onReset: () => void;
}

const cell = "w-full min-w-0";

export default function InputPanel(p: Props) {
  const a = p.algo;
  const upd = (i: number, k: keyof ProcessRow, v: string) =>
    p.setRows(p.rows.map((r, j) => (j === i ? { ...r, [k]: v } : r)));
  const add = () => {
    const n = p.rows.length + 1;
    p.setRows([...p.rows, { pid: `P${n}`, arrival: "0", burst: "1", priority: "1", queue: "0" }]);
  };
  const cols = 3 + (a?.needs_priority ? 1 : 0) + (a?.needs_queue ? 1 : 0);

  return (
    <div className="space-y-4">
      <label className="block text-sm">
        <span className="text-mute">Select Algorithm</span>
        <select className="w-full mt-1" value={p.algoId} onChange={(e) => p.setAlgoId(e.target.value)}>
          {p.algos.map((x) => <option key={x.id} value={x.id}>{x.label}</option>)}
        </select>
      </label>

      {a?.needs_quantum && (
        <label className="block text-sm"><span className="text-mute">Time Quantum (q)</span>
          <input className="w-full mt-1" inputMode="numeric" value={p.quantum} onChange={(e) => p.setQuantum(e.target.value)} /></label>
      )}
      {a?.needs_levels && (
        <label className="block text-sm"><span className="text-mute">Queue quanta, comma separated (use “none” for FCFS)</span>
          <input className="w-full mt-1" placeholder={a.id === "mlq" ? "2,none" : "2,4,8"} value={p.levels} onChange={(e) => p.setLevels(e.target.value)} /></label>
      )}

      <div>
        <p className="text-sm text-mute mb-1">Process Details</p>
        <div className="grid gap-2 items-center text-xs text-mute" style={{ gridTemplateColumns: `repeat(${cols}, 1fr) 28px` }}>
          <span>PID</span><span>Arrival</span><span>Burst</span>
          {a?.needs_priority && <span>Priority</span>}{a?.needs_queue && <span>Queue</span>}<span />
          {p.rows.map((r, i) => (
            <div key={i} className="contents">
              <input className={cell} value={r.pid} onChange={(e) => upd(i, "pid", e.target.value)} aria-label="PID" />
              <input className={cell} inputMode="numeric" value={r.arrival} onChange={(e) => upd(i, "arrival", e.target.value)} aria-label="Arrival time" />
              <input className={cell} inputMode="numeric" value={r.burst} onChange={(e) => upd(i, "burst", e.target.value)} aria-label="Burst time" />
              {a?.needs_priority && <input className={cell} inputMode="numeric" value={r.priority} onChange={(e) => upd(i, "priority", e.target.value)} aria-label="Priority" />}
              {a?.needs_queue && <input className={cell} inputMode="numeric" value={r.queue} onChange={(e) => upd(i, "queue", e.target.value)} aria-label="Queue" />}
              <button className="text-mute hover:text-err" disabled={p.rows.length <= 1} onClick={() => p.setRows(p.rows.filter((_, j) => j !== i))} aria-label="Remove process"><Trash2 size={15} /></button>
            </div>
          ))}
        </div>
        <button onClick={add} className="mt-3 inline-flex items-center gap-1 text-sm text-accent border border-accent/40 rounded-md px-3 py-1.5 hover:bg-accent/10"><Plus size={15} />Add Process</button>
      </div>

      <button onClick={p.onStart} disabled={p.busy}
        className="w-full flex items-center justify-center gap-2 bg-accent text-bg font-semibold rounded-md py-2.5 hover:brightness-110">
        {p.busy ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}Start Simulation
      </button>

      <div className="grid grid-cols-4 gap-2 text-sm">
        <button onClick={p.onPrev} disabled={!p.canPrev} className="border border-line rounded-md py-2 flex justify-center hover:bg-line/40" aria-label="Previous step"><SkipBack size={16} /></button>
        <button onClick={p.onTogglePlay} disabled={!p.hasSim} className="border border-line rounded-md py-2 flex justify-center hover:bg-line/40" aria-label={p.playing ? "Pause" : "Resume"}>{p.playing ? <Pause size={16} /> : <Play size={16} />}</button>
        <button onClick={p.onNext} disabled={!p.canNext} className="border border-line rounded-md py-2 flex justify-center hover:bg-line/40" aria-label="Next step"><SkipForward size={16} /></button>
        <button onClick={p.onReset} className="border border-line rounded-md py-2 flex justify-center hover:bg-line/40" aria-label="Reset"><RotateCcw size={16} /></button>
      </div>
      <label className="flex items-center gap-3 text-sm text-mute">Speed
        <input type="range" min={0.25} max={4} step={0.25} value={p.speed} onChange={(e) => p.setSpeed(Number(e.target.value))} className="flex-1 accent-accent !p-0" />
        <span className="w-10 text-right font-mono">{p.speed}×</span>
      </label>
      <p className="text-xs text-mute">Speed only changes animation timing. Results come from the backend and never change.</p>
    </div>
  );
}
