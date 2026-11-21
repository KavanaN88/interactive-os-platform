import { useEffect, useState } from "react";

/** Plays through an already-computed trace. Speed only changes timing, never results. */
export function usePlayer(length: number) {
  const [step, setStep] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);

  useEffect(() => {
    if (!playing) return;
    if (step >= length - 1) { setPlaying(false); return; }
    const id = setTimeout(() => setStep((s) => s + 1), 1100 / speed);
    return () => clearTimeout(id);
  }, [playing, step, length, speed]);

  return {
    step, setStep, playing, speed, setSpeed,
    load: () => { setStep(0); setPlaying(true); },
    stop: () => { setStep(0); setPlaying(false); },
    toggle: () => { if (step >= length - 1) setStep(0); setPlaying((p) => !p || step >= length - 1); },
    next: () => { setPlaying(false); setStep((s) => Math.min(length - 1, s + 1)); },
    prev: () => { setPlaying(false); setStep((s) => Math.max(0, s - 1)); },
    jump: (i: number) => { setPlaying(false); setStep(i); },
  };
}
export type Player = ReturnType<typeof usePlayer>;
