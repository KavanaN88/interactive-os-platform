/* Pure display components (no icons/fetching). They draw backend trace data and never recompute results. */
import type { GStep } from "../types";
import { pidColor } from "../lib/colors";

// ---------- Page replacement ----------
export function FrameTable({ refs, steps, upto, frames }: { refs: number[]; steps: GStep[]; upto: number; frames: number }) {
  const cols = steps.slice(0, upto + 1);
  return (
    <div className="overflow-x-auto">
      <table className="text-sm border-separate border-spacing-1">
        <thead>
          <tr><th className="text-mute text-xs font-normal text-left pr-2">Page</th>
            {cols.map((s, k) => <th key={k} className={`w-9 h-8 rounded font-mono ${k === upto ? "bg-accent/20 text-accent" : "text-ink"}`}>{refs[k]}</th>)}</tr>
        </thead>
        <tbody>
          {Array.from({ length: frames }, (_, r) => (
            <tr key={r}>
              <td className="text-mute text-xs pr-2">Frame {r}</td>
              {cols.map((s, k) => {
                const v = s.state.frames[r];
                const changed = s.state.slot === r && !s.state.hit;
                const hitCell = s.state.slot === r && s.state.hit;
                const cls = changed ? (s.state.victim !== null ? "bg-warn/25 text-warn border-warn" : "bg-err/20 text-err border-err")
                  : hitCell ? "bg-ok/20 text-ok border-ok" : "border-line text-mute";
                return <td key={k} className={`w-9 h-9 text-center font-mono border rounded ${cls}`}>{v ?? ""}</td>;
              })}
            </tr>
          ))}
          <tr>
            <td className="text-mute text-xs pr-2">Result</td>
            {cols.map((s, k) => <td key={k} className={`text-center text-xs font-semibold rounded ${s.state.hit ? "text-ok" : "text-err"}`}>{s.state.hit ? "HIT" : "FAULT"}</td>)}
          </tr>
        </tbody>
      </table>
      <p className="text-[11px] text-mute mt-1">Green = hit · Red = fault into a free frame · Amber = fault that replaced a page</p>
    </div>
  );
}

export function HitMissTimeline({ timeline, upto }: { timeline: string[]; upto: number }) {
  return (
    <div className="flex flex-wrap gap-1">
      {timeline.map((t, i) => (
        <span key={i} title={`Reference ${i + 1}: ${t === "H" ? "hit" : "fault"}`}
          className={`w-5 h-5 rounded-sm text-[10px] flex items-center justify-center ${i > upto ? "opacity-25" : ""} ${t === "H" ? "bg-ok text-bg" : "bg-err text-bg"}`}>{t}</span>
      ))}
    </div>
  );
}

export function BarsByFrames({ curve }: { curve: { frames: number; faults: number }[] }) {
  const max = Math.max(...curve.map((c) => c.faults), 1);
  return (
    <div className="flex items-end gap-2 h-32">
      {curve.map((c, i) => {
        const up = i > 0 && c.faults > curve[i - 1].faults;
        return (
          <div key={c.frames} className="flex-1 flex flex-col items-center justify-end h-full">
            <span className="text-xs font-mono mb-1">{c.faults}</span>
            <div className={`w-full rounded-t ${up ? "bg-err" : "bg-accent"}`} style={{ height: `${(c.faults / max) * 100}%` }} />
            <span className="text-[11px] text-mute mt-1">{c.frames}f</span>
          </div>
        );
      })}
    </div>
  );
}

// ---------- Disk ----------
export function DiskTrack({ path, maxCyl, requests, upto }: { path: number[]; maxCyl: number; requests: number[]; upto: number }) {
  const W = 700, pad = 24, rowH = 26, H = 50 + path.length * rowH;
  const x = (c: number) => pad + (c / maxCyl) * (W - 2 * pad);
  const y = (k: number) => 40 + k * rowH;
  const shown = path.slice(0, upto + 1);
  const visited = new Set(shown);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Disk head movement">
      <line x1={x(0)} y1={22} x2={x(maxCyl)} y2={22} stroke="#263646" strokeWidth={2} />
      <text x={x(0)} y={14} fontSize={11} fill="#AAB6C5" textAnchor="middle">0</text>
      <text x={x(maxCyl)} y={14} fontSize={11} fill="#AAB6C5" textAnchor="middle">{maxCyl}</text>
      {requests.map((r, i) => (
        <circle key={i} cx={x(r)} cy={22} r={4.5} fill={visited.has(r) ? "#4ADE80" : "#07111D"} stroke="#4ADE80" strokeWidth={1.5}><title>{`request ${r}`}</title></circle>
      ))}
      <polyline fill="none" stroke="#38BDF8" strokeWidth={2} points={shown.map((c, k) => `${x(c)},${y(k)}`).join(" ")} />
      {shown.map((c, k) => (
        <g key={k}>
          <circle cx={x(c)} cy={y(k)} r={k === upto ? 6 : 3.5} fill={k === upto ? "#F59E0B" : "#38BDF8"} />
          <text x={x(c) + 8} y={y(k) + 4} fontSize={10} fill="#AAB6C5">{c}</text>
        </g>
      ))}
    </svg>
  );
}

// ---------- Memory ----------
interface Seg { start: number; size: number; pid: string | null; used: number }
export function MemoryMap({ segments, order, highlight }: { segments: Seg[]; order: string[]; highlight?: number }) {
  const total = segments.reduce((a, s) => a + s.size, 0);
  return (
    <div>
      <div className="flex h-16 rounded-md overflow-hidden border border-line bg-bg">
        {segments.map((s) => (
          <div key={s.start} title={`${s.pid ?? "free"}: ${s.size} KB at ${s.start}`}
            className={`relative flex flex-col items-center justify-center text-[11px] border-r border-bg transition-all duration-300 ${highlight === s.start ? "ring-2 ring-warn ring-inset" : ""}`}
            style={{ width: `${(s.size / total) * 100}%`, minWidth: 18, background: s.pid ? pidColor(s.pid, order) : "repeating-linear-gradient(45deg,#111D2A,#111D2A 6px,#1B2A3A 6px,#1B2A3A 12px)", color: s.pid ? "#07111D" : "#AAB6C5" }}>
            <b>{s.pid ?? "free"}</b><span>{s.size}</span>
            {s.pid && s.size > s.used && <span className="absolute bottom-0 right-0 h-1.5 bg-err/80" style={{ width: `${((s.size - s.used) / s.size) * 100}%` }} title="internal fragmentation" />}
          </div>
        ))}
      </div>
      <div className="flex text-[10px] text-mute font-mono mt-1">
        {segments.map((s) => <span key={s.start} style={{ width: `${(s.size / total) * 100}%`, minWidth: 18 }}>{s.start}</span>)}
      </div>
    </div>
  );
}

// ---------- Deadlock ----------
export function MatrixTable({ title, rows, rowPrefix = "P", colPrefix = "R", mark }: { title: string; rows: number[][]; rowPrefix?: string; colPrefix?: string; mark?: (i: number) => string }) {
  return (
    <div>
      <p className="text-xs text-mute mb-1">{title}</p>
      <table className="text-sm text-center">
        <thead className="text-mute text-xs"><tr><th />{rows[0]?.map((_, j) => <th key={j} className="w-9 font-normal">{colPrefix}{j}</th>)}</tr></thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className={mark?.(i) ?? ""}>
              <td className="text-mute text-xs pr-2 text-left">{rowPrefix}{i}</td>
              {r.map((v, j) => <td key={j} className="border border-line w-9 h-8 font-mono">{v}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

interface GNode { id: string; type: string; instances?: number }
interface GEdge { from: string; to: string; kind: string; count: number }
export function RagGraph({ nodes, edges, cycle }: { nodes: GNode[]; edges: GEdge[]; cycle: string[] }) {
  const procs = nodes.filter((n) => n.type === "process"), ress = nodes.filter((n) => n.type === "resource");
  const W = Math.max(420, Math.max(procs.length, ress.length) * 110), H = 250;
  const pos: Record<string, { x: number; y: number }> = {};
  procs.forEach((n, i) => (pos[n.id] = { x: ((i + 1) * W) / (procs.length + 1), y: 55 }));
  ress.forEach((n, i) => (pos[n.id] = { x: ((i + 1) * W) / (ress.length + 1), y: 195 }));
  const inCycle = (a: string, b: string) => cycle.some((c, i) => c === a && cycle[(i + 1) % cycle.length] === b);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Resource allocation graph">
      <defs>
        {["#AAB6C5", "#F43F5E"].map((c) => <marker key={c} id={`ah${c.slice(1)}`} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill={c} /></marker>)}
      </defs>
      {edges.map((e, i) => {
        const a = pos[e.from], b = pos[e.to];
        const dx = b.x - a.x, dy = b.y - a.y, len = Math.hypot(dx, dy) || 1;
        const hot = inCycle(e.from, e.to), c = hot ? "#F43F5E" : "#AAB6C5";
        const off = e.kind === "request" ? 5 : -5;           // keep opposite edges apart
        const ox = (-dy / len) * off, oy = (dx / len) * off;
        const x1 = a.x + (dx / len) * 22 + ox, y1 = a.y + (dy / len) * 22 + oy, x2 = b.x - (dx / len) * 24 + ox, y2 = b.y - (dy / len) * 24 + oy;
        return (
          <g key={i}>
            <line x1={x1} y1={y1} x2={x2} y2={y2} stroke={c} strokeWidth={hot ? 2.5 : 1.5} strokeDasharray={e.kind === "request" ? "5 4" : undefined} markerEnd={`url(#ah${c.slice(1)})`} />
            {e.count > 1 && <text x={(x1 + x2) / 2 + 6} y={(y1 + y2) / 2} fontSize={11} fill={c}>×{e.count}</text>}
          </g>
        );
      })}
      {procs.map((n) => (
        <g key={n.id}><circle cx={pos[n.id].x} cy={pos[n.id].y} r={20} fill="#111D2A" stroke={cycle.includes(n.id) ? "#F43F5E" : "#38BDF8"} strokeWidth={2} />
          <text x={pos[n.id].x} y={pos[n.id].y + 4} textAnchor="middle" fontSize={12} fill="#F8FAFC">{n.id}</text></g>
      ))}
      {ress.map((n) => (
        <g key={n.id}><rect x={pos[n.id].x - 22} y={pos[n.id].y - 18} width={44} height={36} rx={4} fill="#111D2A" stroke={cycle.includes(n.id) ? "#F43F5E" : "#22D3EE"} strokeWidth={2} />
          <text x={pos[n.id].x} y={pos[n.id].y - 2} textAnchor="middle" fontSize={12} fill="#F8FAFC">{n.id}</text>
          <text x={pos[n.id].x} y={pos[n.id].y + 12} textAnchor="middle" fontSize={9} fill="#AAB6C5">{"● ".repeat(Math.min(n.instances ?? 0, 5)).trim()}{(n.instances ?? 0) > 5 ? "+" : ""}</text></g>
      ))}
    </svg>
  );
}
