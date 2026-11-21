import { useEffect, useMemo, useRef, useState } from "react";
import { BookOpen, CheckCircle2, Circle, Loader2, PlayCircle } from "lucide-react";
import Card from "../components/Card";
import PageHeader from "../components/PageHeader";
import Tabs from "../components/Tabs";
import { get, post, put } from "../lib/api";
import { useAuth } from "../components/AuthProvider";
import type { ModuleId } from "../components/Layout";

interface Mod { id: string; name: string; topics: number }
interface TopicBrief { id: string; module: string; level: string; title: string; summary: string }
interface Topic extends TopicBrief { points: string[]; example: string; exercise: string; answer: string }
interface Question { id: string; type: "mcq" | "numeric"; level: string; prompt: string; options?: string[] }
interface Graded { score: number; total: number; percent: number; by_level: Record<string, { correct: number; total: number }>; results: { id: string; correct: boolean; your_answer: string | null; correct_answer: string; explanation: string; level: string }[] }
interface Attempt { time: string; module: string; level: string; score: number; total: number; percent: number }
const TABS = ["Lessons", "Quiz", "Progress"] as const;
const PKEY = "oslab.progress", HKEY = "oslab.quizHistory";
const read = <T,>(k: string, d: T): T => { try { return JSON.parse(localStorage.getItem(k) ?? "") as T; } catch { return d; } };
const LEVEL_COLOR: Record<string, string> = { beginner: "text-ok border-ok", intermediate: "text-warn border-warn", advanced: "text-err border-err" };

export default function Learn({ onOpen, initialTab = "Lessons" }: { onOpen: (m: ModuleId) => void; initialTab?: (typeof TABS)[number] }) {
  const { user } = useAuth();
  const [tab, setTab] = useState<(typeof TABS)[number]>(initialTab);
  const [mods, setMods] = useState<Mod[]>([]);
  const [all, setAll] = useState<TopicBrief[]>([]);
  const [mod, setMod] = useState("cpu");
  const [topic, setTopic] = useState<Topic | null>(null);
  const [showAns, setShowAns] = useState(false);
  const [done, setDone] = useState<string[]>(() => read<string[]>(PKEY, []));
  const [hist, setHist] = useState<Attempt[]>(() => read<Attempt[]>(HKEY, []));
  const [qMod, setQMod] = useState("cpu");
  const [qLevel, setQLevel] = useState("beginner");
  const [timed, setTimed] = useState(false);
  const [qs, setQs] = useState<Question[] | null>(null);
  const [ans, setAns] = useState<Record<string, string>>({});
  const [graded, setGraded] = useState<Graded | null>(null);
  const [left, setLeft] = useState(0);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const submitRef = useRef<() => void>(() => undefined);

  useEffect(() => { Promise.all([get<Mod[]>("/learn/modules"), get<TopicBrief[]>("/learn/topics")]).then(([m, t]) => { setMods(m); setAll(t); }).catch((e: Error) => setErr(e.message)); }, []);
  const topics = useMemo(() => all.filter((t) => t.module === mod), [all, mod]);
  const open = (id: string) => { setShowAns(false); get<Topic>(`/learn/topics/${id}`).then(setTopic).catch((e: Error) => setErr(e.message)); };
  useEffect(() => { if (topics[0]) open(topics[0].id); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [mod, all.length]);
  const toggleDone = (id: string) => {
    const nowDone = !done.includes(id);
    const n = nowDone ? [...done, id] : done.filter((x) => x !== id);
    setDone(n); localStorage.setItem(PKEY, JSON.stringify(n));
    if (user) put<{ completed: string[] }>("/me/progress", { topic_id: id, completed: nowDone }).catch(() => undefined);   // signed-in progress is also kept on the server
  };
  useEffect(() => {
    if (!user) return;
    get<{ completed: string[] }>("/me/progress").then((r) => setDone((d) => { const n = Array.from(new Set([...d, ...r.completed])); localStorage.setItem(PKEY, JSON.stringify(n)); return n; })).catch(() => undefined);
  }, [user]);

  const startQuiz = async () => {
    setErr(""); setBusy(true); setGraded(null);
    try { const r = await get<{ questions: Question[] }>(`/quiz/${qMod}?level=${qLevel}`); setQs(r.questions); setAns({}); setLeft(timed ? r.questions.length * 60 : 0); }
    catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  };
  const submit = async () => {
    if (!qs) return;
    setBusy(true);
    try {
      const g = await post<Graded>("/quiz/grade", { question_ids: qs.map((q) => q.id), answers: ans, level: qLevel });
      setGraded(g); setQs(null); setLeft(0);
      const h = [{ time: new Date().toLocaleString(), module: qMod, level: qLevel, score: g.score, total: g.total, percent: g.percent }, ...hist].slice(0, 100);
      setHist(h); localStorage.setItem(HKEY, JSON.stringify(h));
    } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  };
  submitRef.current = submit;
  useEffect(() => {
    if (!timed || !qs || left <= 0) return;
    const id = setTimeout(() => { if (left <= 1) submitRef.current(); setLeft((l) => l - 1); }, 1000);
    return () => clearTimeout(id);
  }, [timed, qs, left]);

  const modName = (id: string) => mods.find((m) => m.id === id)?.name ?? id;
  const practice = mods.filter((m) => {
    const a = hist.filter((h) => h.module === m.id);
    const dn = all.filter((t) => t.module === m.id && done.includes(t.id)).length;
    return (a.length > 0 && a.reduce((s, x) => s + x.percent, 0) / a.length < 60) || (dn === 0 && a.length === 0);
  });

  return (
    <div className="max-w-[1300px] mx-auto">
      <PageHeader icon={<BookOpen size={26} />} title="Learning Center" subtitle="Lessons, worked examples and quizzes for all ten Operating System modules." />
      <Tabs tabs={TABS} value={tab} onChange={setTab} />
      {err && <p className="mb-4 p-3 rounded-md border border-err/50 text-err text-sm">{err}</p>}

      {tab === "Lessons" && <div className="grid gap-4 lg:grid-cols-[260px_300px_1fr]">
        <Card title="Modules"><ul className="space-y-1 text-sm">{mods.map((m) => {
          const n = all.filter((t) => t.module === m.id && done.includes(t.id)).length;
          return <li key={m.id}><button onClick={() => setMod(m.id)} className={`w-full text-left px-3 py-2 rounded-md flex justify-between ${mod === m.id ? "bg-accent/15 text-accent" : "hover:bg-line/40"}`}><span>{m.name}</span><span className="text-xs text-mute">{n}/{m.topics}</span></button></li>; })}</ul></Card>
        <Card title={modName(mod)}><ul className="space-y-2">{topics.map((t) => (
          <li key={t.id}><button onClick={() => open(t.id)} className={`w-full text-left border rounded-md p-3 ${topic?.id === t.id ? "border-accent bg-accent/10" : "border-line hover:bg-line/30"}`}>
            <div className="flex items-center gap-2 text-sm">{done.includes(t.id) ? <CheckCircle2 size={16} className="text-ok shrink-0" /> : <Circle size={16} className="text-mute shrink-0" />}<span className="font-medium">{t.title}</span></div>
            <span className={`inline-block mt-2 text-[10px] uppercase border rounded px-1.5 ${LEVEL_COLOR[t.level]}`}>{t.level}</span></button></li>))}</ul></Card>
        <Card title={topic?.title ?? "Lesson"}>{topic ? <div className="space-y-5 text-sm leading-relaxed">
          <span className={`inline-block text-[10px] uppercase border rounded px-1.5 ${LEVEL_COLOR[topic.level]}`}>{topic.level}</span>
          <p>{topic.summary}</p>
          <div><p className="text-xs uppercase text-mute mb-1">Key points</p><ul className="list-disc pl-5 space-y-1">{topic.points.map((p, i) => <li key={i}>{p}</li>)}</ul></div>
          <div className="border border-line rounded-lg p-3 bg-bg"><p className="text-xs uppercase text-mute mb-1">Worked example</p><p>{topic.example}</p></div>
          <div className="border border-accent/40 rounded-lg p-3"><p className="text-xs uppercase text-accent mb-1">Practice question</p><p>{topic.exercise}</p>
            <button className="text-xs text-accent underline mt-2" onClick={() => setShowAns(!showAns)}>{showAns ? "Hide answer" : "Show answer"}</button>{showAns && <p className="mt-2 text-ok">{topic.answer}</p>}</div>
          <div className="flex flex-wrap gap-2">
            <button onClick={() => onOpen(topic.module as ModuleId)} className="inline-flex items-center gap-1.5 bg-accent text-bg font-semibold rounded-md px-4 py-2"><PlayCircle size={16} />Open the simulator</button>
            <button onClick={() => toggleDone(topic.id)} className="inline-flex items-center gap-1.5 border border-line rounded-md px-4 py-2 hover:bg-line/40">{done.includes(topic.id) ? <><CheckCircle2 size={16} className="text-ok" />Completed (undo)</> : <><Circle size={16} />Mark as complete</>}</button></div>
        </div> : <p className="text-mute">Choose a topic.</p>}</Card>
      </div>}

      {tab === "Quiz" && <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
        <Card title="Start a quiz"><div className="space-y-4 text-sm">
          <label className="block"><span className="text-mute">Module</span><select className="w-full mt-1" value={qMod} onChange={(e) => setQMod(e.target.value)}>{mods.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}</select></label>
          <label className="block"><span className="text-mute">Difficulty</span><select className="w-full mt-1" value={qLevel} onChange={(e) => setQLevel(e.target.value)}>{["beginner", "intermediate", "advanced", "all"].map((l) => <option key={l}>{l}</option>)}</select></label>
          <label className="flex items-center gap-2"><input type="checkbox" className="!p-0" checked={timed} onChange={(e) => setTimed(e.target.checked)} />Timed (60 seconds per question)</label>
          <button onClick={startQuiz} disabled={busy} className="w-full flex items-center justify-center gap-2 bg-accent text-bg font-semibold rounded-md py-2.5">{busy && <Loader2 size={16} className="animate-spin" />}Start quiz</button>
          <p className="text-xs text-mute">Multiple-choice and numerical questions. Numerical questions are generated from the simulators, so the numbers differ each time. Correct answers are shown only after you submit.</p></div></Card>
        <div className="space-y-4 min-w-0">
          {!qs && !graded && <Card title="Quiz"><p className="text-sm text-mute py-8 text-center">Pick a module and press Start.</p></Card>}
          {qs && <Card title={`${modName(qMod)} · ${qLevel}`}>
            {timed && <p className={`text-sm font-mono mb-3 ${left <= 15 ? "text-err" : "text-warn"}`}>Time left: {Math.floor(left / 60)}:{String(left % 60).padStart(2, "0")} (the quiz is submitted automatically at 0:00)</p>}
            <ol className="space-y-5 list-decimal pl-5 text-sm">{qs.map((q) => (
              <li key={q.id}><p className="mb-2">{q.prompt} <span className={`ml-1 text-[10px] uppercase border rounded px-1 ${LEVEL_COLOR[q.level]}`}>{q.level}</span></p>
                {q.type === "mcq" ? <div className="space-y-1.5">{q.options?.map((o, i) => <label key={i} className={`flex items-center gap-2 border rounded-md px-3 py-2 cursor-pointer ${ans[q.id] === String(i) ? "border-accent bg-accent/10" : "border-line"}`}>
                  <input type="radio" className="!p-0" name={q.id} checked={ans[q.id] === String(i)} onChange={() => setAns({ ...ans, [q.id]: String(i) })} />{o}</label>)}</div>
                  : <input className="w-48 font-mono" inputMode="decimal" placeholder="your answer" value={ans[q.id] ?? ""} onChange={(e) => setAns({ ...ans, [q.id]: e.target.value })} />}</li>))}</ol>
            <button onClick={submit} disabled={busy} className="mt-5 bg-accent text-bg font-semibold rounded-md px-6 py-2.5">Submit answers</button></Card>}
          {graded && <Card title="Results">
            <p className="text-2xl font-semibold">{graded.score} / {graded.total} <span className={`text-base ${graded.percent >= 60 ? "text-ok" : "text-err"}`}>({graded.percent}%)</span></p>
            <p className="text-sm text-mute mt-1">Correct: {graded.score} · Incorrect: {graded.total - graded.score} · {Object.entries(graded.by_level as Graded["by_level"]).map(([l, v]) => `${l} ${v.correct}/${v.total}`).join(" · ")}</p>
            <ul className="space-y-3 mt-4 text-sm">{graded.results.map((r, i) => <li key={r.id} className={`border rounded-md p-3 ${r.correct ? "border-ok" : "border-err"}`}>
              <p><b>{i + 1}.</b> {r.correct ? <span className="text-ok">Correct</span> : <span className="text-err">Incorrect</span>}{r.your_answer !== null && !r.correct && <span className="text-mute"> · you answered {r.your_answer.length < 20 ? r.your_answer : "…"}</span>}</p>
              {!r.correct && <p className="mt-1">Correct answer: <b>{r.correct_answer}</b></p>}<p className="text-mute mt-1">{r.explanation}</p></li>)}</ul></Card>}
        </div>
      </div>}

      {tab === "Progress" && <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Learning progress"><ul className="space-y-3 text-sm">{mods.map((m) => { const n = all.filter((t) => t.module === m.id && done.includes(t.id)).length;
          return <li key={m.id}><div className="flex justify-between"><span>{m.name}</span><span className="text-mute">{n}/{m.topics} topics</span></div><div className="h-2 bg-bg rounded mt-1"><div className="h-2 rounded bg-ok" style={{ width: `${(n / m.topics) * 100}%` }} /></div></li>; })}</ul></Card>
        <div className="space-y-4">
          <Card title="Concepts that need practice">{practice.length === 0 ? <p className="text-sm text-ok">Nice work: nothing is below 60% and every module has been started.</p> :
            <ul className="space-y-2 text-sm">{practice.map((m) => <li key={m.id} className="flex items-center justify-between border border-line rounded-md px-3 py-2"><span>{m.name}</span><button className="text-accent text-xs underline" onClick={() => { setMod(m.id); setTab("Lessons"); }}>Study</button></li>)}</ul>}</Card>
          <Card title="Quiz history">{hist.length === 0 ? <p className="text-sm text-mute">No quiz attempts yet.</p> :
            <table className="w-full text-xs"><thead className="text-mute"><tr><th className="text-left">When</th><th className="text-left">Module</th><th>Level</th><th>Score</th></tr></thead><tbody>{hist.slice(0, 12).map((h, i) => <tr key={i} className="border-t border-line"><td className="py-1.5">{h.time}</td><td>{modName(h.module)}</td><td className="text-center">{h.level}</td><td className={`text-center ${h.percent >= 60 ? "text-ok" : "text-err"}`}>{h.score}/{h.total}</td></tr>)}</tbody></table>}
            <p className="text-[11px] text-mute mt-2">Progress and history are stored in this browser. Server-side history needs login (not built yet).</p></Card>
        </div>
      </div>}
    </div>
  );
}
