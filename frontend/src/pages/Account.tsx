import { useState, type FormEvent } from "react";
import { Loader2, UserRound } from "lucide-react";
import Card from "../components/Card";
import PageHeader from "../components/PageHeader";
import Tabs from "../components/Tabs";
import { useAuth } from "../components/AuthProvider";

const TABS = ["Sign in", "Create account"] as const;

export default function Account({ onDone, notice }: { onDone: () => void; notice?: string }) {
  const { login, register } = useAuth();
  const [tab, setTab] = useState<(typeof TABS)[number]>("Sign in");
  const [f, setF] = useState({ identifier: "", email: "", username: "", password: "", again: "" });
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof f, v: string) => setF({ ...f, [k]: v });

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setErr("");
    if (tab === "Create account" && f.password !== f.again) { setErr("The two passwords do not match"); return; }
    setBusy(true);
    try {
      if (tab === "Sign in") await login(f.identifier.trim(), f.password);
      else await register(f.email.trim(), f.username.trim(), f.password);
      onDone();
    } catch (x) { setErr((x as Error).message); } finally { setBusy(false); }
  };
  const field = (label: string, key: keyof typeof f, type = "text", auto = "off") => (
    <label className="block text-sm"><span className="text-mute">{label}</span><input className="w-full mt-1" type={type} autoComplete={auto} value={f[key]} onChange={(e) => set(key, e.target.value)} required /></label>
  );
  return (
    <div className="max-w-md mx-auto">
      <PageHeader icon={<UserRound size={26} />} title="Your account" subtitle="Sign in to save progress and quiz results. Administrators manage the platform." />
      <Tabs tabs={TABS} value={tab} onChange={(t) => { setTab(t); setErr(""); }} />
      <Card title={tab}>
        <form onSubmit={submit} className="space-y-4">
          {notice && <p className="text-sm text-warn border border-warn/40 rounded-md p-2">{notice}</p>}
          {tab === "Sign in" ? <>{field("Email or username", "identifier", "text", "username")}{field("Password", "password", "password", "current-password")}</> :
            <>{field("Email", "email", "email", "email")}{field("Username (3–32 characters)", "username", "text", "username")}{field("Password (8+ characters, letters and digits)", "password", "password", "new-password")}{field("Repeat password", "again", "password", "new-password")}</>}
          {err && <p className="text-sm text-err border border-err/40 rounded-md p-2">{err}</p>}
          <button disabled={busy} className="w-full flex items-center justify-center gap-2 bg-accent text-bg font-semibold rounded-md py-2.5">{busy && <Loader2 size={16} className="animate-spin" />}{tab}</button>
          <p className="text-xs text-mute">Guests can use every simulator without an account. Too many wrong passwords lock an account for 15 minutes.</p>
        </form>
      </Card>
    </div>
  );
}
