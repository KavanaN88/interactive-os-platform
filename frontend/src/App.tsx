import { useState } from "react";
import Layout, { type ModuleId, type View } from "./components/Layout";
import Account from "./pages/Account";
import Admin from "./pages/Admin";
import Analyzer from "./pages/Analyzer";
import CpuScheduling from "./pages/CpuScheduling";
import DeadlockManagement from "./pages/DeadlockManagement";
import DiskScheduling from "./pages/DiskScheduling";
import FileSystem from "./pages/FileSystem";
import Home from "./pages/Home";
import Learn from "./pages/Learn";
import MemoryManagement from "./pages/MemoryManagement";
import PageReplacement from "./pages/PageReplacement";
import ProcessManagement from "./pages/ProcessManagement";
import Synchronization from "./pages/Synchronization";
import Terminal from "./pages/Terminal";
import VirtualMemory from "./pages/VirtualMemory";

const PAGES: Record<ModuleId, () => JSX.Element> = {
  cpu: CpuScheduling, process: ProcessManagement, sync: Synchronization, deadlock: DeadlockManagement, memory: MemoryManagement,
  paging: PageReplacement, disk: DiskScheduling, fs: FileSystem, vm: VirtualMemory, perf: Analyzer,
};

export default function App() {
  const [view, setView] = useState<View>("home");
  const [active, setActive] = useState<ModuleId>("cpu");
  const [learnTab, setLearnTab] = useState<"Lessons" | "Quiz">("Lessons");
  const [after, setAfter] = useState<View | null>(null);
  const go = (v: View, tab?: "Lessons" | "Quiz") => { if (tab) setLearnTab(tab); setView(v); };
  const open = (m: ModuleId) => { setActive(m); setView("module"); };
  const Page = PAGES[active];
  return (
    <Layout view={view} onView={go} active={active} onSelect={setActive}>
      {view === "home" && <Home onOpenModule={open} onView={go} />}
      {view === "module" && <Page key={active} />}
      {view === "compare" && <Analyzer />}
      {view === "learn" && <Learn key={learnTab} initialTab={learnTab} onOpen={open} />}
      {view === "terminal" && <Terminal />}
      {view === "admin" && <Admin onSignIn={() => { setAfter("admin"); setView("account"); }} />}
      {view === "account" && <Account notice={after === "admin" ? "Sign in with an administrator account to open the dashboard." : undefined} onDone={() => { setView(after ?? "home"); setAfter(null); }} />}
    </Layout>
  );
}
