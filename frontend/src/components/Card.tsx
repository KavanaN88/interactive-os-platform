import type { ReactNode } from "react";

export default function Card({ title, icon, children, className = "" }: { title: string; icon?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`bg-card border border-line rounded-xl ${className}`}>
      <h2 className="flex items-center gap-2 px-4 py-3 border-b border-line font-semibold text-sm">{icon}{title}</h2>
      <div className="p-4">{children}</div>
    </section>
  );
}
