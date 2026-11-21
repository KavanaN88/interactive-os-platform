export default function Tabs<T extends string>({ tabs, value, onChange }: { tabs: readonly T[]; value: T; onChange: (t: T) => void }) {
  return (
    <div className="flex gap-1 border-b border-line mb-4 overflow-x-auto">
      {tabs.map((t) => (
        <button key={t} onClick={() => onChange(t)} className={`px-4 py-2 text-sm rounded-t-md whitespace-nowrap ${value === t ? "bg-accent/15 text-accent" : "text-mute hover:text-ink"}`}>{t}</button>
      ))}
    </div>
  );
}
