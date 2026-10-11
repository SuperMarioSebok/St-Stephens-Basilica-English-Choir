// Multi-stem player on ONE AudioContext clock. All stems of a tempo variant have the same
// sample length (server guarantees it) and are started with the same `when`, so they stay
// sample-locked: no independently started <audio> elements that can drift apart.
// Playback rate is never changed; slower practice switches to a slower rendered variant.

import { loopedPosition } from "./timeline";

export type Levels = Record<string, number>;

export class StemPlayer {
  private ctx: AudioContext;
  private buffers: Record<string, AudioBuffer> = {};
  private gains: Record<string, GainNode> = {};
  private sources: AudioBufferSourceNode[] = [];
  private startedAt = 0;
  private offset = 0;
  private loop: { start: number; end: number } | null = null;
  playing = false;
  duration = 0;

  constructor() {
    let ctx: AudioContext;
    try {
      // Matching the stems' rate halves memory on phones; fall back if unsupported.
      ctx = new AudioContext({ sampleRate: 22050 });
    } catch {
      ctx = new AudioContext();
    }
    this.ctx = ctx;
  }

  async load(urls: Record<string, string>, onProgress?: (done: number, total: number) => void) {
    const wasPlaying = this.playing;
    const pos = this.position();
    this.stopSources();
    const entries = Object.entries(urls);
    let done = 0;
    const decoded = await Promise.all(
      entries.map(async ([part, url]) => {
        const r = await fetch(url, { credentials: "same-origin" });
        if (!r.ok) throw new Error(`Could not load audio (${r.status})`);
        const buf = await this.ctx.decodeAudioData(await r.arrayBuffer());
        onProgress?.(++done, entries.length);
        return [part, buf] as const;
      }),
    );
    const lengths = new Set(decoded.map(([, b]) => b.length));
    if (lengths.size > 1) throw new Error("Stems have different lengths; playback would not be in sync");
    this.buffers = Object.fromEntries(decoded);
    for (const part of Object.keys(this.buffers)) {
      if (!this.gains[part]) {
        this.gains[part] = this.ctx.createGain();
        this.gains[part].connect(this.ctx.destination);
      }
    }
    this.duration = decoded[0]?.[1].duration ?? 0;
    return { wasPlaying, pos };
  }

  setLevels(levels: Levels) {
    const t = this.ctx.currentTime;
    for (const [part, g] of Object.entries(this.gains)) {
      g.gain.setTargetAtTime(levels[part] ?? 0, t, 0.015);
    }
  }

  position(): number {
    if (!this.playing) return this.offset;
    return loopedPosition(this.offset, this.ctx.currentTime - this.startedAt, this.loop);
  }

  async play(from?: number) {
    await this.ctx.resume(); // must run inside a tap on iOS/Android
    this.stopSources();
    let start = Math.max(0, Math.min(from ?? this.offset, this.duration - 0.05));
    if (this.loop && (start < this.loop.start || start >= this.loop.end)) start = this.loop.start;
    const when = this.ctx.currentTime + 0.06;
    for (const [part, buf] of Object.entries(this.buffers)) {
      const src = this.ctx.createBufferSource();
      src.buffer = buf;
      if (this.loop) {
        src.loop = true;
        src.loopStart = this.loop.start;
        src.loopEnd = this.loop.end;
      }
      src.connect(this.gains[part]);
      src.start(when, start);
      this.sources.push(src);
    }
    this.offset = start;
    this.startedAt = when;
    this.playing = true;
  }

  pause() {
    this.offset = this.position();
    this.stopSources();
    this.playing = false;
  }

  async seek(t: number) {
    this.offset = Math.max(0, Math.min(t, this.duration));
    if (this.playing) await this.play(this.offset);
  }

  async setLoop(loop: { start: number; end: number } | null) {
    this.loop = loop;
    if (this.playing) await this.play(loop ? loop.start : this.position());
    else if (loop) this.offset = loop.start;
  }

  /** Call from an animation frame: stops at the end when not looping. */
  tick(): number {
    const p = this.position();
    if (this.playing && !this.loop && p >= this.duration) {
      this.pause();
      this.offset = 0;
      return 0;
    }
    return p;
  }

  private stopSources() {
    for (const s of this.sources) {
      try {
        s.stop();
      } catch {
        /* already stopped */
      }
      s.disconnect();
    }
    this.sources = [];
  }

  close() {
    this.stopSources();
    void this.ctx.close();
  }
}
