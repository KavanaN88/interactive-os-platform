/* Pure display components for Process, Sync, File System and Virtual Memory. They draw backend data only. */
/* eslint-disable @typescript-eslint/no-explicit-any */
import { pidColor } from "../lib/colors";

export const STATE_COLOR: Record<string, string> = { new: "#AAB6C5", ready: "#F59E0B", running: "#4ADE80", waiting: "#22D3EE", terminated: "#F43F5E" };

// ---------- Process management ----------
const NODES: Record<string, [number, number]> = { new: [60, 60], ready: [230, 60], running: [410, 60], terminated: [580, 60], waiting: [320, 175] };
const EDGES: [string, string, string][] = [["new", "ready", "admit"], ["ready", "running", "dispatch"], ["running", "ready", "preempt"], ["running", "waiting", "I/O request"], ["waiting", "ready", "I/O done"], ["running", "terminated", "exit"]];

export function StateDiagram({ processes, transition }: { processes: Record<string, any>; transition: (string | null)[] | null }) {
  const byState = (s: string) => Object.entries(processes).filter(([, p]) => p.state === s).map(([k]) => k);
  const order = Object.keys(processes);
  return (
    <svg viewBox="0 0 640 270" className="w-full" role="img" aria-label="Process state transition diagram">
      <defs>{["#AAB6C5", "#F59E0B"].map((c) => <marker key={c} id={`sd${c.slice(1)}`} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill={c} /></marker>)}</defs>
      {EDGES.map(([a, b, label]) => {
        const [x1, y1] = NODES[a], [x2, y2] = NODES[b];
        const dx = x2 - x1, dy = y2 - y1, len = Math.hypot(dx, dy), off = a === "running" && b === "ready" ? 9 : a === "ready" && b === "running" ? -9 : 0;
        const ox = (-dy / len) * off, oy = (dx / len) * off, hot = !!transition && transition[0] === a && transition[1] === b, c = hot ? "#F59E0B" : "#AAB6C5";
        return (
          <g key={a + b}>
            <line x1={x1 + (dx / len) * 30 + ox} y1={y1 + (dy / len) * 30 + oy} x2={x2 - (dx / len) * 33 + ox} y2={y2 - (dy / len) * 33 + oy} stroke={c} strokeWidth={hot ? 3 : 1.5} markerEnd={`url(#sd${c.slice(1)})`} />
            <text x={(x1 + x2) / 2 + ox * 2.2} y={(y1 + y2) / 2 + oy * 2.2 - 4} fontSize={10} fill={hot ? "#F59E0B" : "#AAB6C5"} textAnchor="middle">{label}</text>
          </g>
        );
      })}
      {Object.entries(NODES).map(([s, [x, y]]) => {
        const here = byState(s), active = !!transition && transition[1] === s;
        return (
          <g key={s}>
            <circle cx={x} cy={y} r={28} fill="#111D2A" stroke={STATE_COLOR[s]} strokeWidth={active ? 4 : 2} />
            <text x={x} y={y + 4} textAnchor="middle" fontSize={11} fill="#F8FAFC">{s}</text>
            {here.map((p, i) => <g key={p}><rect x={x - 28 + (i % 3) * 38} y={y + 36 + Math.floor(i / 3) * 18} width={36} height={15} rx={3} fill={pidColor(p, order)} /><text x={x - 10 + (i % 3) * 38} y={y + 47 + Math.floor(i / 3) * 18} fontSize={9} textAnchor="middle" fill="#07111D">{p.slice(0, 6)}</text></g>)}
          </g>
        );
      })}
    </svg>
  );
}

export function StateTimeline({ timeline, makespan, upto }: { timeline: Record<string, { state: string; start: number; end: number }[]>; makespan: number; upto: number }) {
  return (
    <div className="space-y-1.5">
      {Object.entries(timeline).map(([pid, segs]) => (
        <div key={pid} className="flex items-center gap-2 text-xs">
          <span className="w-14 truncate text-mute">{pid}</span>
          <div className="relative flex-1 h-5 bg-bg rounded border border-line overflow-hidden">
            {segs.filter((s) => s.state !== "new" && upto > s.start).map((s, i) => (
              <div key={i} title={`${s.state} ${s.start}–${s.end}`} className="absolute top-0 h-full transition-all duration-300"
                style={{ left: `${(s.start / makespan) * 100}%`, width: `${((Math.min(s.end, upto) - s.start) / makespan) * 100}%`, background: STATE_COLOR[s.state] }} />
            ))}
          </div>
        </div>
      ))}
      <div className="flex gap-3 text-[11px] text-mute pt-1">{["ready", "running", "waiting"].map((s) => <span key={s}><i className="inline-block w-2.5 h-2.5 rounded-sm mr-1" style={{ background: STATE_COLOR[s] }} />{s}</span>)}</div>
    </div>
  );
}

export function PcbTable({ processes }: { processes: Record<string, any> }) {
  const hex = (n: number) => "0x" + n.toString(16).toUpperCase();
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs text-center">
        <thead className="text-mute"><tr>{["PID", "State", "Prio", "Mem KB", "PC", "SP", "ACC", "Parent"].map((h) => <th key={h} className="font-medium py-1">{h}</th>)}</tr></thead>
        <tbody>
          {Object.entries(processes).map(([pid, p]) => (
            <tr key={pid} className="border-t border-line">
              <td className="py-1.5 font-medium">{pid}</td>
              <td><span className="px-1.5 py-0.5 rounded text-bg" style={{ background: STATE_COLOR[p.state] }}>{p.state}</span></td>
              <td>{p.priority}</td><td>{p.memory_kb}</td><td className="font-mono">{hex(p.regs.PC)}</td><td className="font-mono">{hex(p.regs.SP)}</td><td>{p.regs.ACC}</td><td>{p.parent ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function ProcessTree({ nodes }: { nodes: { pid: string; children: any[] }[] }) {
  return (
    <ul className="text-sm space-y-1 pl-1">
      {nodes.map((n) => (
        <li key={n.pid}><span className="font-mono">{n.pid}</span>{n.children.length > 0 && <div className="ml-3 pl-3 border-l border-line mt-1"><ProcessTree nodes={n.children} /></div>}</li>
      ))}
    </ul>
  );
}

export function BufferSlots({ items, capacity }: { items: (string | number)[]; capacity: number }) {
  return (
    <div className="flex flex-wrap gap-2">
      {Array.from({ length: capacity }, (_, i) => (
        <div key={i} className={`min-w-14 h-10 px-2 rounded border flex items-center justify-center text-xs font-mono ${i < items.length ? "border-accent bg-accent/15 text-accent" : "border-line text-mute"}`}>{i < items.length ? String(items[i]) : "empty"}</div>
      ))}
    </div>
  );
}

// ---------- Synchronization ----------
const THREAD_COLOR: Record<string, string> = { ready: "#F59E0B", blocked: "#F43F5E", done: "#4ADE80" };
export function SyncState({ state }: { state: Record<string, any> }) {
  const { threads, sems, shared, running } = state;
  const sharedEntries = Object.entries(shared).filter(([k]) => k !== "buffer");
  return (
    <div className="space-y-4 text-sm">
      <div><p className="text-xs text-mute mb-1">Threads</p>
        <div className="flex flex-wrap gap-2">{Object.entries(threads).map(([n, s]) => (
          <span key={n} className={`px-2.5 py-1 rounded border text-xs ${running === n ? "ring-2 ring-accent" : ""}`} style={{ borderColor: THREAD_COLOR[s as string], color: THREAD_COLOR[s as string] }}>{n}: {s as string}</span>))}</div></div>
      {Object.keys(sems).length > 0 && <div><p className="text-xs text-mute mb-1">Semaphores / locks</p>
        <div className="flex flex-wrap gap-2">{Object.entries(sems).map(([n, s]: [string, any]) => (
          <div key={n} className="border border-line rounded-md px-3 py-1.5 text-xs"><b className="font-mono">{n}</b> = <span className="font-mono text-accent">{s.value}</span>
            {s.holders.length > 0 && <span className="text-mute"> · held by {s.holders.join(", ")}</span>}{s.queue.length > 0 && <span className="text-err"> · waiting: {s.queue.join(", ")}</span>}</div>))}</div></div>}
      {shared.buffer && <div><p className="text-xs text-mute mb-1">Bounded buffer</p><BufferSlots items={shared.buffer} capacity={Math.max(shared.buffer.length, state.capacity ?? shared.buffer.length)} /></div>}
      {sharedEntries.length > 0 && <div><p className="text-xs text-mute mb-1">Shared data</p>
        <div className="flex flex-wrap gap-2">{sharedEntries.map(([k, v]) => <span key={k} className="border border-line rounded px-2 py-1 text-xs font-mono">{k} = {JSON.stringify(v)}</span>)}</div></div>}
    </div>
  );
}

// ---------- File system ----------
export function DiskMap({ owners, roles, order, highlight }: { owners: (string | null)[]; roles: (string | null)[]; order: string[]; highlight?: number[] }) {
  const cols = owners.length > 128 ? 32 : 16;
  return (
    <div>
      <div className="grid gap-1" style={{ gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))` }}>
        {owners.map((o, i) => (
          <div key={i} title={`block ${i}: ${o ?? "free"}${roles[i] === "index" ? " (index block)" : ""}`}
            className={`aspect-square rounded-sm text-[9px] flex items-center justify-center ${highlight?.includes(i) ? "ring-2 ring-warn" : ""} ${roles[i] === "index" ? "border-2 border-ink" : "border border-line"}`}
            style={{ background: o ? pidColor(o, order) : "#0B1522", color: o ? "#07111D" : "#4B5B6C" }}>{i}</div>
        ))}
      </div>
      <p className="text-[11px] text-mute mt-1">Coloured = owned by a file · dark = free · white border = index block · amber ring = blocks touched by this step</p>
    </div>
  );
}

export function DirTree({ node, depth = 0 }: { node: any; depth?: number }) {
  return (
    <div style={{ marginLeft: depth ? 14 : 0 }} className="text-sm">
      <div className="py-0.5"><span className="text-mute mr-1">{node.type === "dir" ? "▸" : "·"}</span><span className={node.type === "dir" ? "text-accent" : ""}>{node.name}</span>
        {node.type === "file" && <span className="text-xs text-mute ml-2">{node.size_kb} KB · blocks {node.blocks.join(",")}</span>}</div>
      {node.children?.map((c: any) => <DirTree key={c.path} node={c} depth={depth + 1} />)}
    </div>
  );
}

// ---------- Virtual memory ----------
export function VmTables({ pageTable, tlb, frames, current }: { pageTable: Record<string, any>; tlb: number[][]; frames: (number | null)[]; current?: { page?: number; frame?: number } }) {
  const th = "text-mute font-normal text-xs px-2";
  return (
    <div className="grid md:grid-cols-3 gap-4 text-xs">
      <div><p className="text-mute mb-1">Page table (touched pages)</p>
        <table className="w-full text-center"><thead><tr><th className={th}>Page</th><th className={th}>Frame</th><th className={th}>Valid</th></tr></thead><tbody>
          {Object.entries(pageTable).map(([p, e]) => <tr key={p} className={`border-t border-line ${current?.page === Number(p) ? "bg-accent/15" : ""}`}><td className="py-1">{p}</td><td>{e.valid ? e.frame : "—"}</td><td className={e.valid ? "text-ok" : "text-err"}>{e.valid ? 1 : 0}</td></tr>)}
          {Object.keys(pageTable).length === 0 && <tr><td colSpan={3} className="text-mute py-2">empty</td></tr>}</tbody></table></div>
      <div><p className="text-mute mb-1">TLB</p>
        <table className="w-full text-center"><thead><tr><th className={th}>Page</th><th className={th}>Frame</th></tr></thead><tbody>
          {tlb.map(([p, f]) => <tr key={p} className={`border-t border-line ${current?.page === p ? "bg-accent/15" : ""}`}><td className="py-1">{p}</td><td>{f}</td></tr>)}
          {tlb.length === 0 && <tr><td colSpan={2} className="text-mute py-2">empty</td></tr>}</tbody></table></div>
      <div><p className="text-mute mb-1">Physical frames</p>
        <div className="grid grid-cols-4 gap-1">{frames.map((p, f) => <div key={f} className={`rounded border text-center py-1.5 ${current?.frame === f ? "border-accent bg-accent/15" : "border-line"}`}><span className="text-mute">F{f}</span><br /><b>{p === null ? "—" : `P${p}`}</b></div>)}</div></div>
    </div>
  );
}

export function ValueBars({ rows, valueKey, labelKey, unit = "", mark }: { rows: any[]; valueKey: string; labelKey: string; unit?: string; mark?: (r: any) => boolean }) {
  const max = Math.max(...rows.map((r) => r[valueKey]), 1);
  return (
    <div className="flex items-end gap-1.5 h-40">
      {rows.map((r) => (
        <div key={r[labelKey]} className="flex-1 flex flex-col items-center justify-end h-full min-w-0">
          <span className="text-[10px] font-mono mb-0.5">{r[valueKey]}{unit}</span>
          <div className={`w-full rounded-t ${mark?.(r) ? "bg-err" : "bg-accent"}`} style={{ height: `${(r[valueKey] / max) * 100}%`, minHeight: 2 }} />
          <span className="text-[10px] text-mute mt-1">{r[labelKey]}</span>
        </div>
      ))}
    </div>
  );
}
