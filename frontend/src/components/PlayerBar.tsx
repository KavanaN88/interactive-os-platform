import { Play, Pause, SkipBack, SkipForward, RotateCcw } from "lucide-react";
import type { Player } from "../hooks/usePlayer";

export default function PlayerBar({ player, length, onReset }: { player: Player; length: number; onReset: () => void }) {
  const has = length > 0;
  const btn = "border border-line rounded-md py-2 flex justify-center hover:bg-line/40";
  return (
    <div className="space-y-2">
      <div className="grid grid-cols-4 gap-2">
        <button className={btn} disabled={!has || player.step === 0} onClick={player.prev} aria-label="Previous step"><SkipBack size={16} /></button>
        <button className={btn} disabled={!has} onClick={player.toggle} aria-label={player.playing ? "Pause" : "Play"}>{player.playing ? <Pause size={16} /> : <Play size={16} />}</button>
        <button className={btn} disabled={!has || player.step >= length - 1} onClick={player.next} aria-label="Next step"><SkipForward size={16} /></button>
        <button className={btn} onClick={onReset} aria-label="Reset"><RotateCcw size={16} /></button>
      </div>
      <label className="flex items-center gap-3 text-sm text-mute">Speed
        <input type="range" min={0.25} max={4} step={0.25} value={player.speed} onChange={(e) => player.setSpeed(Number(e.target.value))} className="flex-1 accent-accent !p-0" />
        <span className="w-10 text-right font-mono">{player.speed}×</span>
      </label>
      {has && <p className="text-xs text-mute">Step {player.step + 1} of {length}. Speed changes only animation timing.</p>}
    </div>
  );
}
