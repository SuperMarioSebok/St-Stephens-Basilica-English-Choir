import { describe, expect, it } from "vitest";
import { barIndexAt, convertPosition, loopSeconds, loopedPosition } from "./timeline";
import { barQuarters, nameToMidi, parseBar } from "./synth";

const beat = 60 / 84;
const bars = Array.from({ length: 9 }, (_, i) => ({
  index: i,
  label: String(i),
  pickup: i === 0,
  start: i === 0 ? 0 : beat + (i - 1) * 4 * beat,
}));
const end = 33 * beat;

describe("timeline", () => {
  it("finds the bar at a time", () => {
    expect(barIndexAt(bars, 0)).toBe(0);
    expect(barIndexAt(bars, beat)).toBe(1);
    expect(barIndexAt(bars, beat * 4.9)).toBe(1);
    expect(barIndexAt(bars, end)).toBe(8);
  });

  it("computes loop bounds per tempo variant", () => {
    const l100 = loopSeconds(bars, end, 2, 3, 1);
    expect(l100.start).toBeCloseTo(5 * beat);
    expect(l100.end).toBeCloseTo(13 * beat);
    const l50 = loopSeconds(bars, end, 3, 2, 0.5);
    expect(l50.start).toBeCloseTo(10 * beat);
    expect(l50.end).toBeCloseTo(26 * beat);
    expect(loopSeconds(bars, end, 8, 8, 1).end).toBeCloseTo(end);
  });

  it("keeps the musical position when changing tempo", () => {
    expect(convertPosition(10, 1, 0.5)).toBeCloseTo(20);
    expect(convertPosition(20, 0.5, 0.75)).toBeCloseTo(13.3333, 3);
  });

  it("wraps inside a loop", () => {
    expect(loopedPosition(2, 1, { start: 2, end: 4 })).toBe(3);
    expect(loopedPosition(2, 2.5, { start: 2, end: 4 })).toBe(2.5);
    expect(loopedPosition(2, 2.5, null)).toBe(4.5);
  });
});

describe("bar text", () => {
  it("parses notes, chords, rests and ties like the server", () => {
    const { notes, error } = parseBar("G4:1 R:1 C4+E4:1.5 D5:0.5~");
    expect(error).toBeNull();
    expect(notes.map((n) => n.midi)).toEqual([[67], [], [60, 64], [74]]);
    expect(barQuarters(notes)).toBe(4);
    expect(notes[3].tie).toBe(true);
    expect(nameToMidi("Bb3")).toBe(58);
    expect(parseBar("H4:1").error).not.toBeNull();
  });
});
