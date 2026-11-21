// Mirrors the backend JSON. The frontend only DISPLAYS these values; it never recomputes algorithm results.
export interface ProcessRow { pid: string; arrival: string; burst: string; priority: string; queue: string }

export interface AlgoInfo {
  id: string; label: string; description: string; rules: string[];
  needs_quantum: boolean; needs_priority: boolean; needs_queue: boolean; needs_levels: boolean;
}
export interface StepState { running: string | null; ready: string[]; completed: string[] }
export interface Step { index: number; time: number; event: string; action: string; explanation: string; state: StepState }
export interface GanttSeg { pid: string | null; start: number; end: number }
export interface PerProcess {
  pid: string; arrival: number; burst: number; priority: number;
  start: number; completion: number; turnaround: number; waiting: number; response: number;
}
export interface Metrics {
  avg_waiting_time: number; avg_turnaround_time: number; avg_response_time: number;
  cpu_utilization: number; throughput: number; context_switches: number; makespan: number;
}
export interface SimResponse {
  algorithm: string; steps: Step[]; total_steps: number; truncated: boolean;
  result: { algorithm_label: string; gantt: GanttSeg[]; processes: PerProcess[]; metrics: Metrics };
}
export interface CompareRun { label: string; metrics: Metrics; gantt: GanttSeg[] }
export interface CompareResponse { runs: CompareRun[]; best_by_metric: Record<string, string[]>; explanation: string[] }
export interface ProcessPayload { pid: string; arrival: number; burst: number; priority: number; queue: number }
export interface AlgoConfig { algorithm: string; quantum: number | null; levels: (number | null)[] | null }

// ---- generic shapes used by the Page Replacement, Disk, Memory and Deadlock pages ----
/* eslint-disable @typescript-eslint/no-explicit-any */
export interface GStep { index: number; time: number; event: string; action: string; explanation: string; state: Record<string, any> }
export interface GSim { algorithm: string; input: Record<string, any>; steps: GStep[]; total_steps: number; truncated: boolean; result: Record<string, any> }
export interface GCompare { runs: { label: string; metrics: Record<string, number> }[]; best_by_metric: Record<string, string[]>; explanation: string[] }
export interface CatalogItem { id: string; label: string; description: string }
