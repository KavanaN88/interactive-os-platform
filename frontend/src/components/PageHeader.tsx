import type { ReactNode } from "react";

export default function PageHeader({ icon, title, subtitle, tag }: { icon: ReactNode; title: string; subtitle: string; tag?: string }) {
  return (
    <div className="flex flex-wrap items-center gap-3 mb-4">
      <div className="p-3 rounded-xl bg-accent/15 text-accent">{icon}</div>
      <div className="flex-1 min-w-[220px]"><h1 className="text-xl font-semibold">{title}</h1><p className="text-sm text-mute">{subtitle}</p></div>
      {tag && <span className="text-xs border border-line rounded-md px-3 py-1.5 text-mute">{tag}</span>}
    </div>
  );
}
