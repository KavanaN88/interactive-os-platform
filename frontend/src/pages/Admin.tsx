import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Loader2, ShieldCheck } from "lucide-react";
import Card from "../components/Card";
import Kv from "../components/Kv";
import PageHeader from "../components/PageHeader";
import Tabs from "../components/Tabs";
import { MODULES } from "../components/Layout";
import { useAuth, type User } from "../components/AuthProvider";
import { ValueBars } from "../components/visuals2";
import { del, get, patch, post, put } from "../lib/api";

const TABS = ["Overview", "Users", "Content", "Performance", "Audit log"] as const;
interface Stats { total_users: number; students: number; administrators: number; active_accounts: number; inactive_accounts: number; simulations_total: number; most_used_modules: { module: string; count: number }[]; simulations_per_day: { day: string; count: number }[]; quiz_attempts: number; quiz_participants: number; quiz_average_percent: number | null; learning_completion_percent: number }
interface UserRow { id: string; email: string; username: string; role: "student" | "administrator"; is_active: boolean; created_at: number; last_login_at: number | null }
interface UsersRes { items: UserRow[]; total: number; limit: number; offset: number }
interface Perf { students: { username: string; email: string; quiz_attempts: number; avg_percent: number | null; best_percent: number | null; topics_completed: number; last_login_at: number | null }[]; modules: { module: string; name: string; topics: number; topics_completed: number; students_started: number; completion_percent: number; quiz_attempts: number; avg_quiz_percent: number | null }[]; overall_completion_percent: number }
interface AuditRow { id: number; ts: number; actor_name: string | null; action: string; target: string | null; detail: Record<string, unknown> | null; ip: string | null }
interface TopicRow { id: string; module: string; level: string; title: string; source: string; published: boolean }
interface TopicFull extends TopicRow { summary: string; points: string[]; example: string; exercise: string; answer: string }
interface QuestionRow { id: string; module: string; level: string; prompt: string; options: string[]; correct_index: number; explanation: string; source: string; published: boolean }
type Notify = (msg: string, ok?: boolean) => void;
const when = (t: number | null) => (t ? new Date(t * 1000).toLocaleString() : "never");
const LEVELS = ["beginner", "intermediate", "advanced"];
const modName = (id: string) => MODULES.find((m) => m.id === id)?.name ?? id;
const inputCls = "w-full";

export default function Admin({ onSignIn }: { onSignIn: () => void }) {
  const { user, loading } = useAuth();
  if (loading) return <p className="flex items-center gap-2 text-mute"><Loader2 className="animate-spin" size={16} />Checking your session…</p>;
  if (!user) return (
    <div className="max-w-md mx-auto"><PageHeader icon={<ShieldCheck size={26} />} title="Administrator dashboard" subtitle="Sign in with an administrator account to continue." />
      <Card title="Sign in required"><button onClick={onSignIn} className="bg-accent text-bg font-semibold rounded-md px-5 py-2.5">Go to sign in</button></Card></div>);
  if (user.role !== "administrator") return (
    <div className="max-w-md mx-auto"><PageHeader icon={<ShieldCheck size={26} />} title="Administrator dashboard" subtitle="Restricted area" />
      <Card title="Administrator access required"><p className="text-sm">You are signed in as <b>{user.username}</b> (student). Only administrators can open this page, and the server enforces that on every request.</p></Card></div>);
  return <Dashboard me={user} />;
}

function Dashboard({ me }: { me: User }) {
  const [tab, setTab] = useState<(typeof TABS)[number]>("Overview");
  const [flash, setFlash] = useState<{ msg: string; ok: boolean } | null>(null);
  const notify: Notify = (msg, ok = true) => { setFlash({ msg, ok }); setTimeout(() => setFlash(null), 5000); };
  return (
    <div className="max-w-[1400px] mx-auto">
      <PageHeader icon={<ShieldCheck size={26} />} title="Administrator dashboard" subtitle="Users, content, analytics and audit trail." tag={`Signed in as ${me.username}`} />
      <Tabs tabs={TABS} value={tab} onChange={setTab} />
      {flash && <p role="status" className={`mb-4 rounded-md border p-3 text-sm ${flash.ok ? "border-ok text-ok" : "border-err text-err"}`}>{flash.msg}</p>}
      {tab === "Overview" && <Overview notify={notify} />}
      {tab === "Users" && <Users me={me} notify={notify} />}
      {tab === "Content" && <Content notify={notify} />}
      {tab === "Performance" && <Performance notify={notify} />}
      {tab === "Audit log" && <Audit notify={notify} />}
    </div>
  );
}

function useLoad<T>(load: () => Promise<T>, notify: Notify, deps: unknown[]) {
  const [data, setData] = useState<T | null>(null);
  const reload = useCallback(() => { load().then(setData).catch((e: Error) => notify(e.message, false)); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, deps);
  useEffect(() => { reload(); }, [reload]);
  return [data, reload] as const;
}

function Overview({ notify }: { notify: Notify }) {
  const [s] = useLoad(() => get<Stats>("/admin/stats"), notify, []);
  if (!s) return <p className="text-mute">Loading…</p>;
  const cards: [string, string | number][] = [["Registered students", s.students], ["Administrators", s.administrators], ["Active accounts", s.active_accounts], ["Inactive accounts", s.inactive_accounts],
    ["Simulation executions", s.simulations_total], ["Quiz attempts", s.quiz_attempts], ["Quiz participants", s.quiz_participants], ["Average quiz score", s.quiz_average_percent === null ? "no attempts" : `${s.quiz_average_percent}%`],
    ["Learning completion", `${s.learning_completion_percent}%`]];
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-5 gap-3">{cards.map(([k, v]) => <div key={k} className="border border-line bg-card rounded-xl p-4"><p className="text-xs text-mute">{k}</p><p className="text-2xl font-semibold mt-1">{v}</p></div>)}</div>
      <div className="grid lg:grid-cols-2 gap-4">
        <Card title="Most-used modules">{s.most_used_modules.length ? <ValueBars rows={s.most_used_modules.map((m) => ({ label: modName(m.module).split(" ")[0], count: m.count }))} valueKey="count" labelKey="label" /> : <p className="text-sm text-mute">No simulations recorded yet. Counts appear as soon as anyone runs one.</p>}</Card>
        <Card title="Simulations per day (last 14 days)">{s.simulations_per_day.length ? <ValueBars rows={s.simulations_per_day.map((d) => ({ label: d.day.slice(5), count: d.count }))} valueKey="count" labelKey="label" /> : <p className="text-sm text-mute">No activity yet.</p>}</Card>
      </div>
      <p className="text-xs text-mute">Figures come from real recorded activity: simulation requests, graded quizzes and completed lessons of signed-in students.</p>
    </div>
  );
}

function Users({ me, notify }: { me: User; notify: Notify }) {
  const [q, setQ] = useState(""), [role, setRole] = useState(""), [status, setStatus] = useState(""), [offset, setOffset] = useState(0);
  const [reset, setReset] = useState<{ id: string; pw: string } | null>(null);
  const limit = 15;
  const [res, reload] = useLoad(() => {
    const p = new URLSearchParams({ limit: String(limit), offset: String(offset) });
    if (q.trim()) p.set("search", q.trim());
    if (role) p.set("role", role);
    if (status) p.set("active", status === "active" ? "true" : "false");
    return get<UsersRes>(`/admin/users?${p.toString()}`);
  }, notify, [q, role, status, offset]);
  const act = async (fn: () => Promise<unknown>, ok: string) => { try { await fn(); notify(ok); reload(); } catch (e) { notify((e as Error).message, false); } };
  const submitReset = (e: FormEvent) => { e.preventDefault(); if (reset) act(async () => { await post(`/admin/users/${reset.id}/reset-password`, { new_password: reset.pw }); setReset(null); }, "Password reset. The user's sessions were signed out."); };
  return (
    <Card title={`Users${res ? ` (${res.total})` : ""}`}>
      <div className="flex flex-wrap gap-3 mb-4 text-sm">
        <input className="w-56" placeholder="Search email or username" value={q} onChange={(e) => { setQ(e.target.value); setOffset(0); }} aria-label="Search users" />
        <select value={role} onChange={(e) => { setRole(e.target.value); setOffset(0); }}><option value="">All roles</option><option value="student">Students</option><option value="administrator">Administrators</option></select>
        <select value={status} onChange={(e) => { setStatus(e.target.value); setOffset(0); }}><option value="">Any status</option><option value="active">Active</option><option value="inactive">Inactive</option></select>
      </div>
      <div className="overflow-x-auto"><table className="w-full text-sm"><thead className="text-mute text-xs"><tr><th className="text-left py-1">User</th><th>Role</th><th>Status</th><th>Last sign-in</th><th className="text-right">Actions</th></tr></thead><tbody>
        {res?.items.map((u) => { const self = u.id === me.id; return (
          <tr key={u.id} className="border-t border-line align-top"><td className="py-2"><b>{u.username}</b><br /><span className="text-xs text-mute">{u.email}</span></td>
            <td className="text-center">{u.role}</td><td className={`text-center ${u.is_active ? "text-ok" : "text-err"}`}>{u.is_active ? "active" : "inactive"}</td><td className="text-center text-xs">{when(u.last_login_at)}</td>
            <td className="text-right space-x-2 whitespace-nowrap text-xs">{self ? <span className="text-mute">this is you</span> : <>
              <button className="underline text-accent" onClick={() => act(() => patch(`/admin/users/${u.id}`, { role: u.role === "student" ? "administrator" : "student" }), "Role updated")}>{u.role === "student" ? "Make admin" : "Make student"}</button>
              <button className="underline text-warn" onClick={() => act(() => patch(`/admin/users/${u.id}`, { is_active: !u.is_active }), u.is_active ? "Account deactivated" : "Account activated")}>{u.is_active ? "Deactivate" : "Activate"}</button>
              <button className="underline" onClick={() => setReset({ id: u.id, pw: "" })}>Reset password</button>
              <button className="underline text-err" onClick={() => { if (window.confirm(`Delete ${u.username}? Their progress is removed. This cannot be undone.`)) act(() => del(`/admin/users/${u.id}`), "User deleted"); }}>Delete</button></>}</td></tr>); })}
        {res && res.items.length === 0 && <tr><td colSpan={5} className="py-6 text-center text-mute">No users match.</td></tr>}</tbody></table></div>
      {reset && <form onSubmit={submitReset} className="mt-4 flex flex-wrap gap-2 items-end border border-line rounded-md p-3 text-sm"><label className="flex-1 min-w-[200px]">New password (8+ characters, letters and digits)<input className={inputCls} type="password" autoComplete="new-password" value={reset.pw} onChange={(e) => setReset({ ...reset, pw: e.target.value })} required /></label>
        <button className="bg-accent text-bg font-semibold rounded-md px-4 py-2">Set password</button><button type="button" className="border border-line rounded-md px-4 py-2" onClick={() => setReset(null)}>Cancel</button></form>}
      {res && res.total > limit && <div className="flex items-center gap-3 mt-4 text-sm"><button disabled={offset === 0} className="border border-line rounded px-3 py-1" onClick={() => setOffset(Math.max(0, offset - limit))}>Previous</button>
        <span className="text-mute">{offset + 1}–{Math.min(offset + limit, res.total)} of {res.total}</span><button disabled={offset + limit >= res.total} className="border border-line rounded px-3 py-1" onClick={() => setOffset(offset + limit)}>Next</button></div>}
    </Card>
  );
}

const BLANK_TOPIC = { module: "cpu", level: "beginner", title: "", summary: "", points: "", example: "", exercise: "", answer: "", published: true };
const BLANK_Q = { module: "cpu", level: "beginner", prompt: "", options: "", correct: "0", explanation: "", published: true };

function Content({ notify }: { notify: Notify }) {
  const [sub, setSub] = useState<"Lessons" | "Questions">("Lessons");
  const [mod, setMod] = useState("");
  const [topics, reloadT] = useLoad(() => get<TopicRow[]>("/admin/topics"), notify, []);
  const [questions, reloadQ] = useLoad(() => get<QuestionRow[]>("/admin/questions"), notify, []);
  const [tf, setTf] = useState<(typeof BLANK_TOPIC & { id?: string }) | null>(null);
  const [qf, setQf] = useState<(typeof BLANK_Q & { id?: string }) | null>(null);
  const act = async (fn: () => Promise<unknown>, ok: string, after: () => void) => { try { await fn(); notify(ok); after(); } catch (e) { notify((e as Error).message, false); } };
  const modSel = <select value={mod} onChange={(e) => setMod(e.target.value)} aria-label="Filter by module"><option value="">All modules</option>{MODULES.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}</select>;

  const editTopic = async (id: string) => { try { const t = await get<TopicFull>(`/admin/topics/${id}`); setTf({ id, module: t.module, level: t.level, title: t.title, summary: t.summary, points: t.points.join("\n"), example: t.example, exercise: t.exercise, answer: t.answer, published: t.published }); } catch (e) { notify((e as Error).message, false); } };
  const saveTopic = (e: FormEvent) => { e.preventDefault(); if (!tf) return;
    const body = { module: tf.module, level: tf.level, title: tf.title, summary: tf.summary, points: tf.points.split("\n").map((x) => x.trim()).filter(Boolean), example: tf.example, exercise: tf.exercise, answer: tf.answer, published: tf.published };
    act(() => (tf.id ? put(`/admin/topics/${tf.id}`, body) : post("/admin/topics", body)), tf.id ? "Lesson updated" : "Lesson created", () => { setTf(null); reloadT(); }); };
  const saveQuestion = (e: FormEvent) => { e.preventDefault(); if (!qf) return;
    const body = { module: qf.module, level: qf.level, prompt: qf.prompt, options: qf.options.split("\n").map((x) => x.trim()).filter(Boolean), correct_index: Number(qf.correct), explanation: qf.explanation, published: qf.published };
    act(() => (qf.id ? put(`/admin/questions/${encodeURIComponent(qf.id)}`, body) : post("/admin/questions", body)), qf.id ? "Question updated" : "Question created", () => { setQf(null); reloadQ(); }); };
  const opts = qf ? qf.options.split("\n").map((x) => x.trim()).filter(Boolean) : [];
  const txt = (label: string, v: string, set: (s: string) => void, rows = 2) => <label className="block text-sm"><span className="text-mute">{label}</span><textarea rows={rows} className="w-full mt-1 bg-bg border border-line rounded-md p-2 outline-none focus:border-accent" value={v} onChange={(e) => set(e.target.value)} required /></label>;
  const sel = (label: string, v: string, set: (s: string) => void, options: [string, string][]) => <label className="block text-sm"><span className="text-mute">{label}</span><select className="w-full mt-1" value={v} onChange={(e) => set(e.target.value)}>{options.map(([a, b]) => <option key={a} value={a}>{b}</option>)}</select></label>;

  return (
    <div className="space-y-4">
      <Tabs tabs={["Lessons", "Questions"] as const} value={sub} onChange={setSub} />
      {sub === "Lessons" && <Card title="Learning materials">
        <div className="flex flex-wrap gap-3 mb-3 items-center">{modSel}<button className="bg-accent text-bg font-semibold rounded-md px-4 py-1.5 text-sm" onClick={() => setTf({ ...BLANK_TOPIC })}>New lesson</button></div>
        <div className="overflow-x-auto"><table className="w-full text-sm"><thead className="text-mute text-xs"><tr><th className="text-left py-1">Title</th><th>Module</th><th>Level</th><th>Source</th><th>Visible</th><th className="text-right">Actions</th></tr></thead><tbody>
          {topics?.filter((t) => !mod || t.module === mod).map((t) => (
            <tr key={t.id} className="border-t border-line"><td className="py-1.5">{t.title}</td><td className="text-center">{modName(t.module)}</td><td className="text-center">{t.level}</td><td className="text-center text-xs">{t.source}</td>
              <td className={`text-center ${t.published ? "text-ok" : "text-err"}`}>{t.published ? "yes" : "hidden"}</td>
              <td className="text-right space-x-2 whitespace-nowrap text-xs"><button className="underline text-warn" onClick={() => act(() => post(`/admin/topics/${t.id}/visibility`, { published: !t.published }), t.published ? "Lesson hidden from learners" : "Lesson published", reloadT)}>{t.published ? "Hide" : "Publish"}</button>
                {t.source === "custom" && <><button className="underline text-accent" onClick={() => editTopic(t.id)}>Edit</button><button className="underline text-err" onClick={() => { if (window.confirm(`Delete "${t.title}"?`)) act(() => del(`/admin/topics/${t.id}`), "Lesson deleted", reloadT); }}>Delete</button></>}</td></tr>))}</tbody></table></div>
        {tf && <form onSubmit={saveTopic} className="mt-5 border border-line rounded-lg p-4 space-y-3"><h4 className="font-semibold">{tf.id ? "Edit lesson" : "New lesson"}</h4>
          <div className="grid sm:grid-cols-2 gap-3">{sel("Module", tf.module, (v) => setTf({ ...tf, module: v }), MODULES.map((m) => [m.id, m.name]))}{sel("Level", tf.level, (v) => setTf({ ...tf, level: v }), LEVELS.map((l) => [l, l]))}</div>
          <label className="block text-sm"><span className="text-mute">Title</span><input className="w-full mt-1" value={tf.title} onChange={(e) => setTf({ ...tf, title: e.target.value })} required /></label>
          {txt("Summary", tf.summary, (v) => setTf({ ...tf, summary: v }), 3)}{txt("Key points (one per line)", tf.points, (v) => setTf({ ...tf, points: v }), 4)}{txt("Worked example", tf.example, (v) => setTf({ ...tf, example: v }))}
          {txt("Practice question", tf.exercise, (v) => setTf({ ...tf, exercise: v }))}{txt("Answer", tf.answer, (v) => setTf({ ...tf, answer: v }))}
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" className="!p-0" checked={tf.published} onChange={(e) => setTf({ ...tf, published: e.target.checked })} />Visible to learners</label>
          <div className="flex gap-2"><button className="bg-accent text-bg font-semibold rounded-md px-5 py-2">Save lesson</button><button type="button" className="border border-line rounded-md px-5 py-2" onClick={() => setTf(null)}>Cancel</button></div></form>}
      </Card>}
      {sub === "Questions" && <Card title="Quiz questions">
        <div className="flex flex-wrap gap-3 mb-3 items-center">{modSel}<button className="bg-accent text-bg font-semibold rounded-md px-4 py-1.5 text-sm" onClick={() => setQf({ ...BLANK_Q })}>New question</button></div>
        <div className="overflow-x-auto"><table className="w-full text-sm"><thead className="text-mute text-xs"><tr><th className="text-left py-1">Question</th><th>Module</th><th>Level</th><th>Source</th><th>Visible</th><th className="text-right">Actions</th></tr></thead><tbody>
          {questions?.filter((q) => !mod || q.module === mod).map((q) => (
            <tr key={q.id} className="border-t border-line"><td className="py-1.5 max-w-[420px]">{q.prompt}</td><td className="text-center">{modName(q.module)}</td><td className="text-center">{q.level}</td><td className="text-center text-xs">{q.source}</td>
              <td className={`text-center ${q.published ? "text-ok" : "text-err"}`}>{q.published ? "yes" : "hidden"}</td>
              <td className="text-right space-x-2 whitespace-nowrap text-xs"><button className="underline text-warn" onClick={() => act(() => post(`/admin/questions/${encodeURIComponent(q.id)}/visibility`, { published: !q.published }), q.published ? "Question hidden" : "Question published", reloadQ)}>{q.published ? "Hide" : "Publish"}</button>
                {q.source === "custom" && <><button className="underline text-accent" onClick={() => setQf({ id: q.id, module: q.module, level: q.level, prompt: q.prompt, options: q.options.join("\n"), correct: String(q.correct_index), explanation: q.explanation, published: q.published })}>Edit</button>
                  <button className="underline text-err" onClick={() => { if (window.confirm("Delete this question?")) act(() => del(`/admin/questions/${encodeURIComponent(q.id)}`), "Question deleted", reloadQ); }}>Delete</button></>}</td></tr>))}</tbody></table></div>
        {qf && <form onSubmit={saveQuestion} className="mt-5 border border-line rounded-lg p-4 space-y-3"><h4 className="font-semibold">{qf.id ? "Edit question" : "New multiple-choice question"}</h4>
          <div className="grid sm:grid-cols-2 gap-3">{sel("Module", qf.module, (v) => setQf({ ...qf, module: v }), MODULES.map((m) => [m.id, m.name]))}{sel("Level", qf.level, (v) => setQf({ ...qf, level: v }), LEVELS.map((l) => [l, l]))}</div>
          {txt("Question", qf.prompt, (v) => setQf({ ...qf, prompt: v }))}{txt("Answer options (one per line, 2–6)", qf.options, (v) => setQf({ ...qf, options: v }), 4)}
          {sel("Correct answer", qf.correct, (v) => setQf({ ...qf, correct: v }), opts.length ? opts.map((o, i) => [String(i), `${i + 1}. ${o}`] as [string, string]) : [["0", "Add options first"]])}
          {txt("Explanation shown after submission", qf.explanation, (v) => setQf({ ...qf, explanation: v }))}
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" className="!p-0" checked={qf.published} onChange={(e) => setQf({ ...qf, published: e.target.checked })} />Visible in quizzes</label>
          <div className="flex gap-2"><button className="bg-accent text-bg font-semibold rounded-md px-5 py-2">Save question</button><button type="button" className="border border-line rounded-md px-5 py-2" onClick={() => setQf(null)}>Cancel</button></div></form>}
      </Card>}
    </div>
  );
}

function Performance({ notify }: { notify: Notify }) {
  const [p] = useLoad(() => get<Perf>("/admin/performance"), notify, []);
  if (!p) return <p className="text-mute">Loading…</p>;
  return (
    <div className="space-y-4">
      <Card title="Module completion report"><Kv items={[["Overall learning completion", `${p.overall_completion_percent}%`]]} />
        <div className="overflow-x-auto mt-3"><table className="w-full text-sm text-center"><thead className="text-mute text-xs"><tr><th className="text-left py-1">Module</th><th>Lessons</th><th>Students started</th><th>Completion</th><th>Quiz attempts</th><th>Avg quiz score</th></tr></thead><tbody>
          {p.modules.map((m) => <tr key={m.module} className="border-t border-line"><td className="text-left py-1.5">{m.name}</td><td>{m.topics}</td><td>{m.students_started}</td><td>{m.completion_percent}%</td><td>{m.quiz_attempts}</td><td>{m.avg_quiz_percent === null ? "—" : `${m.avg_quiz_percent}%`}</td></tr>)}</tbody></table></div></Card>
      <Card title={`Student performance (${p.students.length})`}><div className="overflow-x-auto"><table className="w-full text-sm text-center"><thead className="text-mute text-xs"><tr><th className="text-left py-1">Student</th><th>Quiz attempts</th><th>Average</th><th>Best</th><th>Lessons completed</th><th>Last sign-in</th></tr></thead><tbody>
        {p.students.map((s) => <tr key={s.email} className="border-t border-line"><td className="text-left py-1.5">{s.username}<br /><span className="text-xs text-mute">{s.email}</span></td><td>{s.quiz_attempts}</td><td>{s.avg_percent === null ? "—" : `${s.avg_percent}%`}</td><td>{s.best_percent === null ? "—" : `${s.best_percent}%`}</td><td>{s.topics_completed}</td><td className="text-xs">{when(s.last_login_at)}</td></tr>)}
        {p.students.length === 0 && <tr><td colSpan={6} className="py-6 text-mute">No students have registered yet.</td></tr>}</tbody></table></div></Card>
    </div>
  );
}

function Audit({ notify }: { notify: Notify }) {
  const [filter, setFilter] = useState("");
  const [rows] = useLoad(() => get<AuditRow[]>(`/admin/audit?limit=200&action=${encodeURIComponent(filter)}`), notify, [filter]);
  return (
    <Card title="Audit log">
      <input className="w-72 mb-3 text-sm" placeholder="Filter by action prefix, e.g. admin. or auth." value={filter} onChange={(e) => setFilter(e.target.value)} aria-label="Filter audit log" />
      <div className="overflow-x-auto"><table className="w-full text-xs"><thead className="text-mute"><tr><th className="text-left py-1">Time</th><th className="text-left">Who</th><th className="text-left">Action</th><th className="text-left">Target</th><th className="text-left">Details</th><th className="text-left">IP</th></tr></thead><tbody>
        {rows?.map((r) => <tr key={r.id} className="border-t border-line align-top"><td className="py-1.5 whitespace-nowrap">{when(r.ts)}</td><td>{r.actor_name ?? "—"}</td><td className="font-mono">{r.action}</td><td>{r.target ?? ""}</td><td className="font-mono text-mute">{r.detail ? JSON.stringify(r.detail) : ""}</td><td>{r.ip ?? ""}</td></tr>)}
        {rows && rows.length === 0 && <tr><td colSpan={6} className="py-6 text-center text-mute">Nothing logged yet.</td></tr>}</tbody></table></div>
    </Card>
  );
}
