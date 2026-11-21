import { useEffect, useRef } from "react";
import type { Step } from "../types";
import { EVENT_COLOR } from "../lib/colors";

interface Props { steps: Pick<Step, "index" | "time" | "event" | "explanation">[]; active: number; onSelect: (i: number) => void }

export default function StepList({ steps, active, onSelect }: Props) {
  const ref = useRef<HTMLButtonElement | null>(null);
  useEffect(() => { ref.current?.scrollIntoView({ block: "nearest" }); }, [active]);
  return (
    <div className="max-h-64 overflow-y-auto pr-1 space-y-1">
      {steps.map((s, i) => (
        <button key={s.index} ref={i === active ? ref : undefined} onClick={() => onSelect(i)}
          className={`w-full text-left px-3 py-2 rounded-md text-sm flex gap-3 border ${
            i === active ? "bg-accent/15 border-accent/50" : "border-transparent hover:bg-line/40"} ${i > active ? "opacity-50" : ""}`}>
          <span className="font-mono text-mute shrink-0">t = {s.time}</span>
          <span className={`shrink-0 w-20 ${EVENT_COLOR[s.event] ?? "text-mute"}`}>{s.event}</span>
          <span className="text-ink/90">{s.explanation}</span>
        </button>
      ))}
    </div>
  );
}
