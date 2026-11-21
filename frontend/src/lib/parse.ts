export function parseIntList(text: string, label: string): number[] {
  const parts = text.split(/[,\s]+/).filter(Boolean);
  if (parts.length === 0) throw new Error(`${label}: enter at least one number`);
  return parts.map((p) => {
    const n = Number(p);
    if (!Number.isInteger(n)) throw new Error(`${label}: "${p}" is not a whole number`);
    return n;
  });
}

export function toInt(v: string, label: string): number {
  const n = Number(v);
  if (v.trim() === "" || !Number.isInteger(n)) throw new Error(`${label} must be a whole number`);
  return n;
}

export interface MemOp { op: "alloc" | "free" | "compact"; pid?: string; size?: number }

/** Lines: "alloc P1 212", "free P1", "compact". Blank lines and # comments are ignored. */
export function parseOps(text: string): MemOp[] {
  const ops: MemOp[] = [];
  text.split("\n").forEach((raw, i) => {
    const line = raw.replace(/#.*/, "").trim();
    if (!line) return;
    const [cmd, pid, size] = line.split(/\s+/);
    const c = cmd.toLowerCase();
    if (c === "compact") ops.push({ op: "compact" });
    else if (c === "free" && pid) ops.push({ op: "free", pid });
    else if (c === "alloc" && pid && size) ops.push({ op: "alloc", pid, size: toInt(size, `Line ${i + 1} size`) });
    else throw new Error(`Line ${i + 1}: use "alloc PID SIZE", "free PID" or "compact"`);
  });
  return ops;
}

export interface FsOp { op: string; path: string; size?: number }
/** Lines: mkdir /p · create /p KB · append /p KB · read /p · delete /p */
export function parseFsOps(text: string): FsOp[] {
  const out: FsOp[] = [];
  text.split("\n").forEach((raw, i) => {
    const line = raw.replace(/#.*/, "").trim();
    if (!line) return;
    const [cmd, path, size] = line.split(/\s+/);
    const c = (cmd ?? "").toLowerCase();
    if (!path || !["mkdir", "create", "append", "read", "delete"].includes(c)) throw new Error(`Line ${i + 1}: use mkdir, create, append, read or delete followed by a path`);
    if (c === "create" || c === "append") out.push({ op: c, path, size: toInt(size ?? "", `Line ${i + 1} size (KB)`) });
    else out.push({ op: c, path });
  });
  return out;
}

export interface IpcOpIn { by: string; op: string; key?: string; data?: string | number }
/** pipe / queue lines: "W send hello" · "R recv".  shared memory: "A write x 5" · "B read x" */
export function parseIpcOps(text: string, mechanism: string): IpcOpIn[] {
  const out: IpcOpIn[] = [];
  text.split("\n").forEach((raw, i) => {
    const line = raw.replace(/#.*/, "").trim();
    if (!line) return;
    const t = line.split(/\s+/);
    if (t.length < 2) throw new Error(`Line ${i + 1}: write "<process> <operation> ..."`);
    const [by, op] = t;
    if (mechanism === "shared_memory") {
      if (!t[2]) throw new Error(`Line ${i + 1}: shared memory needs a slot name, e.g. "A write x 5"`);
      out.push(op === "write" ? { by, op, key: t[2], data: t[3] ?? "" } : { by, op, key: t[2] });
    } else out.push(op === "send" ? { by, op, data: t.slice(2).join(" ") } : { by, op });
  });
  return out;
}
