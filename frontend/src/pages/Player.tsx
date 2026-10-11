import { useEffect, useMemo, useRef, useState } from "react";
import { assetUrl, get, PART_NAMES, PARTS, type Me, type Part, type VersionDetail } from "../lib/api";
import { StemPlayer, type Levels } from "../lib/engine";
import { barIndexAt, barName, convertPosition, formatTime, loopSeconds } from "../lib/timeline";
import ScoreView from "./ScoreView";
import ManualPlayer from "./ManualPlayer";
import VideoList from "./VideoList";

type Mode = "solo" | "prominent" | "full";

export function levelsFor(part: Part, mode: Mode, available: Part[], mutes: Set<Part>, solos: Set<Part>): Levels {
  const out: Levels = {};
  for (const p of available) {
    let g = mode === "full" ? 0.8 : p === part ? 1 : mode === "prominent" ? 0.3 : 0;
    if (solos.size > 0) g = solos.has(p) ? Math.max(g, 0.8) : 0;
    if (mutes.has(p)) g = 0;
    out[p] = g;
  }
  return out;
}

export default function Player({ versionId, me, embedded }: { versionId: number; me: Me; embedded?: boolean }) {
  const [detail, setDetail] = useState<VersionDetail | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    get<VersionDetail>(`/api/versions/${versionId}`).then(setDetail).catch((e) => setError(e.message));
  }, [versionId]);
  if (error) return <p className="error">{error}</p>;
  if (!detail) return <p>Loading…</p>;
  if (detail.kind === "manual") return <ManualPlayer detail={detail} embedded={embedded} />;
  if (!detail.timeline || !detail.assets.some((a) => a.kind === "stem"))
    return <p className="muted">Audio for this version is not ready yet.</p>;
  return <ScorePlayer detail={detail} me={me} embedded={embedded} />;
}

function ScorePlayer({ detail, me, embedded }: { detail: VersionDetail; me: Me; embedded?: boolean }) {
  const available = PARTS.filter((p) => detail.parts?.[p]);
  const [part, setPart] = useState<Part>(
    me.voice_part && available.includes(me.voice_part) ? me.voice_part : available.includes("T") ? "T" : available[0],
  );
  const [mode, setMode] = useState<Mode>("prominent");
  const [tempo, setTempo] = useState(100);
  const [mutes, setMutes] = useState<Set<Part>>(new Set());
  const [solos, setSolos] = useState<Set<Part>>(new Set());
  const [pos, setPos] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [loading, setLoading] = useState("");
  const [loopOn, setLoopOn] = useState(false);
  const [loopFrom, setLoopFrom] = useState(1);
  const [loopTo, setLoopTo] = useState(Math.min(2, (detail.timeline?.bars.length ?? 1) - 1));
  const [showScore, setShowScore] = useState(!embedded);
  const [err, setErr] = useState("");
  const engine = useRef<StemPlayer | null>(null);
  const tempoRef = useRef(100);
  const bars = detail.timeline!.bars;
  const end = detail.timeline!.end;
  const factor = tempo / 100;

  useEffect(() => {
    engine.current = new StemPlayer();
    return () => engine.current?.close();
  }, []);

  // Load the stems for the chosen tempo; keep the musical position when switching.
  useEffect(() => {
    const eng = engine.current!;
    const urls: Record<string, string> = {};
    for (const a of detail.assets) if (a.kind === "stem" && a.tempo === tempo && a.part) urls[a.part] = assetUrl(a.id);
    let cancelled = false;
    setLoading("Loading audio…");
    const prevFactor = tempoRef.current / 100;
    eng
      .load(urls, (d, t) => setLoading(`Loading audio ${d}/${t}…`))
      .then(async ({ wasPlaying, pos: oldPos }) => {
        if (cancelled) return;
        tempoRef.current = tempo;
        eng.setLevels(levelsFor(part, mode, available, mutes, solos));
        if (loopOn) await eng.setLoop(loopSeconds(bars, end, loopFrom, loopTo, tempo / 100));
        const newPos = convertPosition(oldPos, prevFactor, tempo / 100);
        if (wasPlaying) await eng.play(newPos);
        else await eng.seek(newPos);
        setLoading("");
      })
      .catch((e) => setErr(e.message));
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tempo, detail]);

  useEffect(() => {
    engine.current?.setLevels(levelsFor(part, mode, available, mutes, solos));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [part, mode, mutes, solos]);

  useEffect(() => {
    void engine.current?.setLoop(loopOn ? loopSeconds(bars, end, loopFrom, loopTo, factor) : null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loopOn, loopFrom, loopTo]);

  useEffect(() => {
    let raf = 0;
    const step = () => {
      const eng = engine.current;
      if (eng) {
        setPos(eng.tick());
        setPlaying(eng.playing);
      }
      raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, []);

  const current = barIndexAt(bars, pos * factor);
  const duration = engine.current?.duration ?? end / factor;
  const toggle = (set: Set<Part>, p: Part, fn: (s: Set<Part>) => void) => {
    const n = new Set(set);
    if (n.has(p)) n.delete(p);
    else n.add(p);
    fn(n);
  };
  const name = PART_NAMES[part];
  const modeLabels: Record<Mode, string> = useMemo(
    () => ({ solo: `${name} alone`, prominent: `${name} louder`, full: "Full choir" }),
    [name],
  );

  return (
    <div className="stack player">
      {!embedded && <h1>{detail.title}</h1>}
      {err && <p className="error">{err}</p>}

      <section>
        <h2 className="label">My part</h2>
        <div className="seg">
          {available.map((p) => (
            <button key={p} className={p === part ? "on" : ""} onClick={() => setPart(p)}>
              {detail.parts?.[p] ?? PART_NAMES[p]}
            </button>
          ))}
        </div>
      </section>

      <section>
        <h2 className="label">Listen to</h2>
        <div className="seg">
          {(["solo", "prominent", "full"] as Mode[]).map((m) => (
            <button key={m} className={m === mode ? "on" : ""} onClick={() => setMode(m)}>
              {modeLabels[m]}
            </button>
          ))}
        </div>
      </section>

      <section className="transport">
        <div className="barnow" aria-live="polite">
          Bar <strong>{barName(bars[current])}</strong>
          <span className="muted"> · {formatTime(pos)} / {formatTime(duration)}</span>
        </div>
        <input
          type="range"
          aria-label="Position"
          min={0}
          max={duration}
          step={0.05}
          value={Math.min(pos, duration)}
          onChange={(e) => void engine.current?.seek(Number(e.target.value))}
        />
        <div className="row">
          <button className="big" aria-label="Back to start" onClick={() => void engine.current?.seek(loopOn ? loopSeconds(bars, end, loopFrom, loopTo, factor).start : 0)}>
            ⏮
          </button>
          <button
            className="big primary grow"
            disabled={!!loading}
            onClick={() => (playing ? engine.current?.pause() : void engine.current?.play())}
          >
            {loading || (playing ? "Pause" : "Play")}
          </button>
        </div>
      </section>

      <section>
        <h2 className="label">Speed (same pitch)</h2>
        <div className="seg">
          {detail.tempos.map((t) => (
            <button key={t} className={t === tempo ? "on" : ""} onClick={() => setTempo(t)}>
              {t === 100 ? "Normal" : `${t}%`}
            </button>
          ))}
        </div>
      </section>

      <section>
        <h2 className="label">Repeat bars</h2>
        <div className="row wrap">
          <label className="inline">
            From
            <select value={loopFrom} onChange={(e) => setLoopFrom(Number(e.target.value))}>
              {bars.map((b) => <option key={b.index} value={b.index}>{barName(b)}</option>)}
            </select>
          </label>
          <label className="inline">
            to
            <select value={loopTo} onChange={(e) => setLoopTo(Number(e.target.value))}>
              {bars.map((b) => <option key={b.index} value={b.index}>{barName(b)}</option>)}
            </select>
          </label>
          <button className={loopOn ? "on" : ""} onClick={() => setLoopOn(!loopOn)}>
            {loopOn ? "Repeating ✓" : "Repeat"}
          </button>
        </div>
      </section>

      <section>
        <h2 className="label">Jump to bar</h2>
        <div className="bars">
          {bars.map((b) => (
            <button
              key={b.index}
              className={b.index === current ? "on" : ""}
              onClick={() => void engine.current?.seek(b.start / factor)}
            >
              {b.label}
            </button>
          ))}
        </div>
      </section>

      <details>
        <summary>Mute or solo single parts</summary>
        <table className="mixer">
          <tbody>
            {available.map((p) => (
              <tr key={p}>
                <th>{detail.parts?.[p]}</th>
                <td>
                  <button className={mutes.has(p) ? "on" : ""} onClick={() => toggle(mutes, p, setMutes)}>
                    Mute
                  </button>
                </td>
                <td>
                  <button className={solos.has(p) ? "on" : ""} onClick={() => toggle(solos, p, setSolos)}>
                    Solo
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>

      <section>
        <button onClick={() => setShowScore(!showScore)}>{showScore ? "Hide score" : "Show score"}</button>
        {showScore && <ScoreView assets={detail.assets} />}
        <p className="muted small">
          The score shows bar numbers. There is no moving cursor yet, because its timing has not been verified;
          use the bar display above.
        </p>
      </section>

      {!embedded && detail.assets.some((a) => a.kind === "video") && (
        <details>
          <summary>Practice videos</summary>
          <VideoList assets={detail.assets} preferPart={part} />
        </details>
      )}

      {!embedded && (
        <a className="button" href={`#/feedback/${detail.song_id}?bar=${encodeURIComponent(bars[current].label)}`}>
          Report a problem in bar {bars[current].label}
        </a>
      )}
    </div>
  );
}
