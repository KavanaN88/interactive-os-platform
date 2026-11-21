import { useEffect, useRef, useState } from "react";
import { Terminal as TerminalIcon } from "lucide-react";
import Card from "../components/Card";
import PageHeader from "../components/PageHeader";
import { post } from "../lib/api";

interface Line { text: string; kind: "cmd" | "out" | "err" }
interface Reply { output: string[]; ok: boolean; clear: boolean }
const QUICK = ["help", "os-info", "process create P1 5", "process create P2 3", "process list", "scheduler run rr 2", "memory status", "filesystem create /a 3", "disk status", "deadlock check"];
const sessionId = () => {
  let s = sessionStorage.getItem("oslab.session");
  if (!s) { s = (crypto.randomUUID?.() ?? `s-${Math.random().toString(16).slice(2)}${Date.now()}`).replace(/[^A-Za-z0-9-]/g, "").padEnd(12, "0"); sessionStorage.setItem("oslab.session", s); }
  return s;
};

export default function Terminal() {
  const [lines, setLines] = useState<Line[]>([{ text: "OS LAB Terminal. Everything runs inside the simulation. Type 'help' for commands.", kind: "out" }]);
  const [input, setInput] = useState("");
  const [hist, setHist] = useState<string[]>([]);
  const [pos, setPos] = useState(-1);
  const [busy, setBusy] = useState(false);
  const end = useRef<HTMLDivElement>(null);
  const box = useRef<HTMLInputElement>(null);
  useEffect(() => { end.current?.scrollIntoView({ block: "end" }); }, [lines]);

  const exec = async (cmd: string) => {
    const c = cmd.trim();
    if (!c) return;
    setLines((l) => [...l, { text: `os-lab$ ${c}`, kind: "cmd" }]);
    setHist((h) => [...h, c]); setPos(-1); setInput(""); setBusy(true);
    try {
      const r = await post<Reply>("/terminal/exec", { session_id: sessionId(), command: c });
      if (r.clear) setLines([]);
      else setLines((l) => [...l, ...r.output.map((t) => ({ text: t, kind: (r.ok ? "out" : "err") as Line["kind"] }))]);
    } catch (e) { setLines((l) => [...l, { text: (e as Error).message, kind: "err" }]); } finally { setBusy(false); box.current?.focus(); }
  };
  const onKey = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") exec(input);
    else if (e.key === "ArrowUp" && hist.length) { e.preventDefault(); const p = pos < 0 ? hist.length - 1 : Math.max(0, pos - 1); setPos(p); setInput(hist[p]); }
    else if (e.key === "ArrowDown" && pos >= 0) { e.preventDefault(); const p = pos + 1; if (p >= hist.length) { setPos(-1); setInput(""); } else { setPos(p); setInput(hist[p]); } }
  };

  return (
    <div className="max-w-[1100px] mx-auto">
      <PageHeader icon={<TerminalIcon size={26} />} title="OS LAB Terminal" subtitle="A safe command line for the simulated OS. Only the supported commands run; nothing touches your computer." />
      <Card title="Terminal">
        <div className="bg-bg border border-line rounded-lg p-3 h-[460px] overflow-y-auto font-mono text-sm cursor-text" onClick={() => box.current?.focus()}>
          {lines.map((l, i) => <pre key={i} className={`whitespace-pre-wrap break-words m-0 ${l.kind === "cmd" ? "text-accent" : l.kind === "err" ? "text-err" : "text-ink"}`}>{l.text}</pre>)}
          <div className="flex items-center gap-2 mt-1"><span className="text-accent">os-lab$</span>
            <input ref={box} autoFocus className="flex-1 !bg-transparent !border-0 !px-0 font-mono text-ink outline-none" value={input} disabled={busy} onChange={(e) => setInput(e.target.value)} onKeyDown={onKey} spellCheck={false} autoComplete="off" aria-label="Terminal input" maxLength={200} /></div>
          <div ref={end} />
        </div>
        <div className="flex flex-wrap gap-2 mt-3">{QUICK.map((q) => <button key={q} onClick={() => exec(q)} disabled={busy} className="text-xs border border-line rounded px-2 py-1 hover:bg-line/40 font-mono">{q}</button>)}</div>
        <p className="text-xs text-mute mt-3">↑ / ↓ browse history · <span className="font-mono">clear</span> empties the screen · shell syntax such as ; | &amp; $ ` is rejected on purpose. Processes you create use simulated memory and the CPU scheduler; files go to a virtual disk and generate disk requests.</p>
      </Card>
    </div>
  );
}
