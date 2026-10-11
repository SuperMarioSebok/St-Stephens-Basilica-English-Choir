// Tiny preview synth for the Voice Lead editor: plays "before" and "after" bar text
// instantly, with the same simple tone for both sides so the comparison is fair.
// It is a preview only; the real practice audio is rendered by the worker.

const STEPS: Record<string, number> = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 };
const ACC: Record<string, number> = { "": 0, "#": 1, "##": 2, b: -1, bb: -2 };
const TOKEN = /^(R|[A-G](?:##|#|bb|b)?-?\d(?:\+[A-G](?:##|#|bb|b)?-?\d)*):([0-9]+(?:\.[0-9]+)?(?:\/[0-9]+)?)(~?)$/;

export interface PNote {
  midi: number[];
  quarters: number;
  tie: boolean;
}

export function nameToMidi(name: string): number {
  const m = /^([A-G])(##|#|bb|b)?(-?\d)$/.exec(name);
  if (!m) throw new Error(`Not a pitch: ${name}`);
  return 12 * (Number(m[3]) + 1) + STEPS[m[1]] + ACC[m[2] ?? ""];
}

function parseDur(s: string): number {
  if (s.includes("/")) {
    const [a, b] = s.split("/").map(Number);
    return a / b;
  }
  return Number(s);
}

/** Parse bar text; returns null and an error message instead of throwing. */
export function parseBar(text: string): { notes: PNote[]; error: string | null } {
  const notes: PNote[] = [];
  for (const tok of text.trim().split(/\s+/).filter(Boolean)) {
    const m = TOKEN.exec(tok);
    if (!m) return { notes, error: `Cannot read "${tok}". Examples: G4:1  F#3:0.5  R:2  C4+E4:1  D5:2~` };
    const midi = m[1] === "R" ? [] : m[1].split("+").map(nameToMidi);
    notes.push({ midi, quarters: parseDur(m[2]), tie: m[3] === "~" });
  }
  return { notes, error: notes.length ? null : "Empty bar" };
}

export function barQuarters(notes: PNote[]): number {
  return notes.reduce((a, n) => a + n.quarters, 0);
}

let ctx: AudioContext | null = null;
let playingNodes: OscillatorNode[] = [];

export function stopPreview() {
  for (const o of playingNodes) {
    try {
      o.stop();
    } catch {
      /* ignore */
    }
  }
  playingNodes = [];
}

/** Play several bars (arrays of notes) back to back at `bpm`. Returns duration in seconds. */
export async function playBars(bars: PNote[][], bpm: number, gapAfter = 0): Promise<number> {
  ctx = ctx ?? new AudioContext();
  await ctx.resume();
  stopPreview();
  const spq = 60 / bpm;
  let t = ctx.currentTime + 0.08;
  const t0 = t;
  for (const bar of bars) {
    for (const n of bar) {
      const len = n.quarters * spq;
      for (const midi of n.midi) {
        const osc = ctx.createOscillator();
        const g = ctx.createGain();
        osc.type = "triangle";
        osc.frequency.value = 440 * Math.pow(2, (midi - 69) / 12);
        g.gain.setValueAtTime(0, t);
        g.gain.linearRampToValueAtTime(0.25 / Math.max(1, n.midi.length), t + 0.02);
        g.gain.setValueAtTime(0.25 / Math.max(1, n.midi.length), t + Math.max(0.03, len - (n.tie ? 0 : 0.05)));
        g.gain.linearRampToValueAtTime(0, t + len);
        osc.connect(g).connect(ctx.destination);
        osc.start(t);
        osc.stop(t + len + 0.01);
        playingNodes.push(osc);
      }
      t += len;
    }
  }
  return t - t0 + gapAfter;
}
