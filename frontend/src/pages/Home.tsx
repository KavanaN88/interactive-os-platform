import { useRef } from "react";
import { ArrowRight, BarChart3, BookOpen, GraduationCap, LayoutGrid, Play, Terminal as TerminalIcon, Zap } from "lucide-react";
import { MODULES, type ModuleId, type View } from "../components/Layout";

interface Props { onOpenModule: (m: ModuleId) => void; onView: (v: View, tab?: "Lessons" | "Quiz") => void }
const SCREEN: ModuleId[] = ["cpu", "process", "memory", "disk", "sync", "deadlock", "fs", "vm"];

export default function Home({ onOpenModule, onView }: Props) {
  const modules = useRef<HTMLElement>(null);
  const features = [
    { icon: Zap, label: "Step-by-Step Simulation", go: () => onOpenModule("cpu") },
    { icon: BarChart3, label: "Algorithm Comparison", go: () => onView("compare") },
    { icon: GraduationCap, label: "Learn & Assess", go: () => onView("learn") },
    { icon: TerminalIcon, label: "Operating System Terminal", go: () => onView("terminal") },
  ];
  const cards = [
    { icon: BookOpen, title: "Learning Center", text: "Study OS concepts with detailed notes, examples, and practical exercises.", go: () => onView("learn", "Lessons") },
    { icon: TerminalIcon, title: "Operating System Terminal", text: "Execute simulated OS commands and explore system operations.", go: () => onView("terminal") },
    { icon: BarChart3, title: "Quiz & Assessment", text: "Test your knowledge with topic-wise quizzes and track your progress.", go: () => onView("learn", "Quiz") },
  ];
  return (
    <div className="bg-[radial-gradient(ellipse_at_top_right,rgba(34,211,238,0.13),transparent_55%),radial-gradient(ellipse_at_bottom_left,rgba(56,189,248,0.07),transparent_50%)]">
      <div className="max-w-[1300px] mx-auto px-5 md:px-8 py-8 md:py-12 space-y-10">
        <section className="grid lg:grid-cols-2 gap-10 items-center">
          <div>
            <span className="inline-block border border-cyan/50 text-cyan rounded-lg px-4 py-1.5 text-sm tracking-wide">Interactive · Visual · Practical</span>
            <h1 className="text-5xl md:text-6xl font-bold mt-6 leading-tight">Operating <span className="text-cyan">System</span></h1>
            <h2 className="text-2xl md:text-3xl font-semibold mt-3 leading-snug">Advanced Operating System<br />Simulator &amp; Visualizer</h2>
            <p className="text-mute mt-5 max-w-xl leading-relaxed">A complete, interactive platform to learn, experiment, and visualize core Operating System concepts and algorithms through real-time simulations.</p>
            <div className="flex flex-wrap gap-3 mt-8">
              <button onClick={() => onOpenModule("cpu")} className="inline-flex items-center gap-2 bg-cyan text-bg font-semibold rounded-lg px-7 py-3 hover:brightness-110"><Play size={18} />Get Started</button>
              <button onClick={() => modules.current?.scrollIntoView({ behavior: "smooth" })} className="inline-flex items-center gap-2 border border-ink/70 rounded-lg px-7 py-3 hover:bg-ink/10"><LayoutGrid size={18} />View Modules</button>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-10">
              {features.map(({ icon: Icon, label, go }) => (
                <button key={label} onClick={go} className="flex flex-col items-center text-center gap-2 text-sm text-ink/90 hover:text-cyan"><Icon size={30} className="text-cyan" /><span>{label}</span></button>
              ))}
            </div>
          </div>
          <div className="mx-auto w-full max-w-[560px] hidden sm:block" style={{ perspective: "1200px" }} aria-hidden="true">
            <div style={{ transform: "rotateY(-16deg) rotateX(5deg)", transformStyle: "preserve-3d" }}>
              <div className="rounded-2xl border-2 border-cyan/70 bg-[#06141f] p-4 shadow-[0_0_70px_rgba(34,211,238,0.35)]">
                <p className="text-center font-semibold mb-3">Operating System</p>
                <div className="grid grid-cols-4 gap-2">
                  {SCREEN.map((id) => { const m = MODULES.find((x) => x.id === id)!; const Icon = m.icon; return (
                    <div key={id} className="border border-cyan/30 rounded-lg bg-cyan/5 py-3 px-1 flex flex-col items-center gap-1.5 text-center"><Icon size={22} className="text-cyan" /><span className="text-[10px] leading-tight text-ink/90">{m.short}</span></div>); })}
                </div>
              </div>
              <div className="h-3 mx-8 rounded-b-xl bg-gradient-to-b from-cyan/60 to-cyan/5" />
            </div>
          </div>
        </section>

        <section ref={modules} className="border border-cyan/30 rounded-2xl bg-card/70 p-5">
          <div className="flex items-center justify-between mb-4"><h3 className="text-lg font-semibold">Operating System Modules</h3>
            <button onClick={() => onOpenModule("cpu")} className="text-cyan text-sm inline-flex items-center gap-1 hover:underline">Explore All <ArrowRight size={15} /></button></div>
          <div className="grid grid-cols-2 sm:grid-cols-5 lg:grid-cols-10 gap-3">
            {MODULES.map(({ id, short, icon: Icon }) => (
              <button key={id} onClick={() => onOpenModule(id)} className={`border rounded-xl py-4 px-2 flex flex-col items-center gap-2 text-center text-xs hover:bg-cyan/10 hover:border-cyan ${id === "cpu" ? "border-cyan bg-cyan/10" : "border-line"}`}>
                <Icon size={26} className="text-cyan" /><span>{short}</span></button>
            ))}
          </div>
        </section>

        <section className="grid md:grid-cols-3 gap-4">
          {cards.map(({ icon: Icon, title, text, go }) => (
            <button key={title} onClick={go} className="text-left border border-cyan/30 rounded-2xl bg-card/70 p-5 flex items-center gap-4 hover:border-cyan hover:bg-cyan/5">
              <span className="p-3 rounded-xl bg-cyan/15 text-cyan"><Icon size={28} /></span>
              <span className="flex-1"><b className="block text-base">{title}</b><span className="text-sm text-mute">{text}</span></span>
              <ArrowRight size={18} className="text-cyan shrink-0" />
            </button>
          ))}
        </section>
      </div>
    </div>
  );
}
