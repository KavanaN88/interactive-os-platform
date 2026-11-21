import type { GanttSeg } from "../types";
import { pidColor } from "../lib/colors";

interface Props { gantt: GanttSeg[]; makespan: number; time: number; order: string[] }

/** Draws backend-provided Gantt segments, revealed up to the current simulation time. */
export default function GanttChart({ gantt, makespan, time, order }: Props) {
  const tickEvery = makespan <= 20 ? 1 : makespan <= 60 ? 5 : Math.ceil(makespan / 12);
  const ticks: number[] = [];
  for (let t = 0; t <= makespan; t += tickEvery) ticks.push(t);
  if (ticks[ticks.length - 1] !== makespan) ticks.push(makespan);

  return (
    <div>
      <div className="relative h-12 rounded-md bg-bg border border-line overflow-hidden">
        {gantt.map((s, i) => {
          if (time <= s.start) return null;
          const shown = Math.min(s.end, time) - s.start;
          const w = (shown / makespan) * 100;
          return (
            <div key={i} title={`${s.pid ?? "IDLE"}: ${s.start}–${s.end}`}
              className="absolute top-0 h-full flex items-center justify-center text-xs font-semibold text-bg border-r border-bg/60 transition-all duration-300"
              style={{ left: `${(s.start / makespan) * 100}%`, width: `${w}%`, background: pidColor(s.pid, order),
                       color: s.pid === null ? "#AAB6C5" : "#07111D" }}>
              {w > 3.5 ? (s.pid ?? "idle") : ""}
            </div>
          );
        })}
      </div>
      <div className="relative h-6 mt-1 text-[11px] text-mute font-mono">
        {ticks.map((t) => (
          <span key={t} className="absolute -translate-x-1/2" style={{ left: `${(t / makespan) * 100}%` }}>{t}</span>
        ))}
      </div>
    </div>
  );
}
