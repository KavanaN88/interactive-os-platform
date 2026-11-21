import type { Metrics, PerProcess } from "../types";

export function ResultsTable({ rows }: { rows: PerProcess[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm text-center">
        <thead className="text-mute text-xs">
          <tr>{["PID", "CT", "TAT", "WT", "RT"].map((h) => <th key={h} className="py-1 font-medium">{h}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.pid} className="border-t border-line">
              <td className="py-1.5 font-medium">{r.pid}</td><td>{r.completion}</td><td>{r.turnaround}</td><td>{r.waiting}</td><td>{r.response}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="text-[11px] text-mute mt-2">CT completion · TAT turnaround · WT waiting · RT response</p>
    </div>
  );
}

export function MetricsList({ m }: { m: Metrics }) {
  const items: [string, string][] = [
    ["Average Waiting Time", String(m.avg_waiting_time)],
    ["Average Turnaround Time", String(m.avg_turnaround_time)],
    ["Average Response Time", String(m.avg_response_time)],
    ["CPU Utilization", `${m.cpu_utilization}%`],
    ["Throughput", `${m.throughput} process/unit`],
    ["Context Switches", String(m.context_switches)],
  ];
  return (
    <ul className="space-y-2 text-sm">
      {items.map(([k, v]) => (
        <li key={k} className="flex justify-between"><span className="text-mute">{k}</span><span className="font-semibold">{v}</span></li>
      ))}
    </ul>
  );
}
