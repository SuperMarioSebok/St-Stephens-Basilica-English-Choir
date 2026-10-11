// Pure timeline maths shared by the player. One canonical timeline (seconds at 100% tempo)
// comes from the server; slower variants were rendered from the score, so every time in
// a variant is exactly time100 / factor.

import type { TimelineBar } from "./api";

export function barIndexAt(bars: TimelineBar[], time100: number): number {
  let idx = 0;
  for (let i = 0; i < bars.length; i++) {
    if (bars[i].start <= time100 + 1e-6) idx = i;
    else break;
  }
  return idx;
}

export function barEnd(bars: TimelineBar[], end: number, i: number): number {
  return i + 1 < bars.length ? bars[i + 1].start : end;
}

/** Loop bounds in seconds of the variant playing at `factor` (1, 0.75, 0.5). */
export function loopSeconds(bars: TimelineBar[], end: number, from: number, to: number, factor: number) {
  const a = Math.min(from, to);
  const b = Math.max(from, to);
  return { start: bars[a].start / factor, end: barEnd(bars, end, b) / factor };
}

/** Keep the musical position when switching tempo variant. */
export function convertPosition(pos: number, fromFactor: number, toFactor: number): number {
  return (pos * fromFactor) / toFactor;
}

/** Where a looping player is after `elapsed` seconds from `offset`. */
export function loopedPosition(offset: number, elapsed: number, loop: { start: number; end: number } | null) {
  const pos = offset + elapsed;
  if (!loop || pos < loop.end) return pos;
  const len = loop.end - loop.start;
  return loop.start + ((pos - loop.start) % len);
}

export function barName(b: TimelineBar): string {
  return b.pickup ? `${b.label} (pickup)` : b.label;
}

export function formatTime(s: number): string {
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return `${m}:${sec.toString().padStart(2, "0")}`;
}
