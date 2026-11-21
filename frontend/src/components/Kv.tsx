export default function Kv({ items }: { items: [string, string | number][] }) {
  return (
    <ul className="space-y-2 text-sm">
      {items.map(([k, v]) => (
        <li key={k} className="flex justify-between gap-3"><span className="text-mute">{k}</span><span className="font-semibold text-right">{v}</span></li>
      ))}
    </ul>
  );
}
