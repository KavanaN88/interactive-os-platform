const PALETTE = ["#38BDF8", "#4ADE80", "#F59E0B", "#C084FC", "#F472B6", "#22D3EE", "#FB923C", "#A3E635"];

export function pidColor(pid: string | null, order: string[]): string {
  if (pid === null) return "#1B2A3A";
  const i = Math.max(0, order.indexOf(pid));
  return PALETTE[i % PALETTE.length];
}

export const EVENT_COLOR: Record<string, string> = {
  arrive: "text-accent", dispatch: "text-ok", complete: "text-ok", preempt: "text-warn",
  quantum: "text-warn", demote: "text-warn", idle: "text-mute",
  hit: "text-ok", fault: "text-err", replace: "text-warn", start: "text-accent", service: "text-ok", boundary: "text-warn", jump: "text-warn",
  init: "text-accent", alloc: "text-ok", alloc_failed: "text-err", error: "text-err", free: "text-warn", compact: "text-cyan",
  safe: "text-ok", unsafe: "text-err", deadlock: "text-err", terminate: "text-warn", recovered: "text-ok",
};
