import { useState, type ReactNode } from "react";
import { Cpu, Users, GitMerge, ShieldAlert, HardDrive, Layers, Disc, FolderTree, MemoryStick, BarChart3, Menu, LogOut, UserRound } from "lucide-react";
import { useAuth } from "./AuthProvider";

export type ModuleId = "cpu" | "process" | "sync" | "deadlock" | "memory" | "paging" | "disk" | "fs" | "vm" | "perf";
export type View = "home" | "module" | "compare" | "learn" | "terminal" | "admin" | "account";

export const MODULES: { id: ModuleId; name: string; short: string; icon: typeof Cpu }[] = [
  { id: "cpu", name: "CPU Scheduling", short: "CPU Scheduling", icon: Cpu },
  { id: "process", name: "Process Management", short: "Process Management", icon: Users },
  { id: "sync", name: "Process Synchronization", short: "Process Synchronization", icon: GitMerge },
  { id: "deadlock", name: "Deadlock Management", short: "Deadlock Management", icon: ShieldAlert },
  { id: "memory", name: "Memory Management", short: "Memory Management", icon: HardDrive },
  { id: "paging", name: "Page Replacement", short: "Page Replacement", icon: Layers },
  { id: "disk", name: "Disk Scheduling", short: "Disk Scheduling", icon: Disc },
  { id: "fs", name: "File System", short: "File System", icon: FolderTree },
  { id: "vm", name: "Virtual Memory", short: "Virtual Memory", icon: MemoryStick },
  { id: "perf", name: "Performance Analyzer", short: "Performance Analyzer", icon: BarChart3 },
];
const TOP: { id: View; label: string }[] = [{ id: "home", label: "Simulator" }, { id: "compare", label: "Compare" }, { id: "learn", label: "Learn" }, { id: "terminal", label: "Terminal" }, { id: "admin", label: "Admin" }];
const WITH_SIDEBAR: View[] = ["module", "compare", "learn", "terminal"];

interface Props { view: View; onView: (v: View) => void; active: ModuleId; onSelect: (id: ModuleId) => void; children: ReactNode }

export default function Layout({ view, onView, active, onSelect, children }: Props) {
  const [open, setOpen] = useState(false);
  const [menu, setMenu] = useState(false);
  const { user, logout } = useAuth();
  const sidebar = WITH_SIDEBAR.includes(view);
  const topActive = (id: View) => (id === "home" ? view === "home" || view === "module" : view === id);
  return (
    <div className="min-h-screen flex flex-col">
      <header className="h-14 border-b border-line bg-side flex items-center px-4 gap-4 sticky top-0 z-30">
        {sidebar && <button className="lg:hidden text-mute" onClick={() => setOpen(!open)} aria-label="Toggle menu"><Menu size={20} /></button>}
        <button onClick={() => onView("home")} className="flex items-center gap-2 font-semibold text-lg" aria-label="Home"><Cpu className="text-accent" size={22} />OS Lab</button>
        <nav className="flex gap-1 mx-auto overflow-x-auto">
          {TOP.map((t) => (
            <button key={t.id} onClick={() => onView(t.id)} className={`px-3 py-1.5 rounded-md text-sm whitespace-nowrap ${topActive(t.id) ? "bg-accent/15 text-accent" : "text-ink hover:bg-line/40"}`}>{t.label}</button>
          ))}
        </nav>
        <div className="relative">
          {user ? (
            <>
              <button onClick={() => setMenu(!menu)} className="flex items-center gap-2 border border-line rounded-full pl-2 pr-3 py-1 text-sm hover:bg-line/40" aria-label="Account menu"><UserRound size={16} className="text-accent" /><span className="hidden sm:inline">{user.username}</span></button>
              {menu && (
                <div className="absolute right-0 mt-2 w-56 bg-card border border-line rounded-lg shadow-xl p-2 text-sm z-40">
                  <p className="px-3 py-2 text-mute">{user.email}<br /><span className="text-xs uppercase">{user.role}</span></p>
                  {user.role === "administrator" && <button className="w-full text-left px-3 py-2 rounded hover:bg-line/40" onClick={() => { setMenu(false); onView("admin"); }}>Admin dashboard</button>}
                  <button className="w-full text-left px-3 py-2 rounded hover:bg-line/40 flex items-center gap-2" onClick={async () => { setMenu(false); await logout(); onView("home"); }}><LogOut size={15} />Sign out</button>
                </div>
              )}
            </>
          ) : (
            <button onClick={() => onView("account")} className="border border-accent/60 text-accent rounded-md px-3 py-1.5 text-sm hover:bg-accent/10">Sign in</button>
          )}
        </div>
      </header>
      <div className="flex flex-1">
        {sidebar && (
          <aside className={`${open ? "block" : "hidden"} lg:block w-64 shrink-0 bg-side border-r border-line p-3 absolute lg:static z-20 top-14 bottom-0`}>
            <p className="text-xs uppercase tracking-wide text-mute px-2 mb-2">Operating System Modules</p>
            {MODULES.map(({ id, name, icon: Icon }) => (
              <button key={id} onClick={() => { onSelect(id); onView("module"); setOpen(false); }}
                className={`w-full text-left flex items-center gap-3 px-3 py-2 rounded-md text-sm mb-0.5 ${view === "module" && id === active ? "bg-accent/15 text-accent" : "text-ink hover:bg-line/40"}`}>
                <Icon size={17} /><span className="flex-1">{name}</span>
              </button>
            ))}
          </aside>
        )}
        <main className={`flex-1 min-w-0 ${view === "home" ? "" : "p-4 md:p-6"}`}>{children}</main>
      </div>
    </div>
  );
}
