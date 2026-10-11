import { useEffect, useRef, useState } from "react";
import { assetUrl, type VersionDetail } from "../lib/api";
import { formatTime } from "../lib/timeline";

// Fallback for an authorized recording + PDF. Loops are by TIME only: we do not know
// where the bars are in a recording and do not pretend to.
export default function ManualPlayer({ detail, embedded }: { detail: VersionDetail; embedded?: boolean }) {
  const audio = useRef<HTMLAudioElement>(null);
  const [pos, setPos] = useState(0);
  const [dur, setDur] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [a, setA] = useState<number | null>(null);
  const [b, setB] = useState<number | null>(null);
  const [rate, setRate] = useState(1);
  const track = detail.assets.find((x) => x.kind === "source_audio");
  const pdf = detail.assets.find((x) => x.kind === "pdf");
  // Only offer slower speeds where the browser promises to keep the pitch.
  const canKeepPitch =
    typeof HTMLMediaElement !== "undefined" &&
    ("preservesPitch" in HTMLMediaElement.prototype || "webkitPreservesPitch" in HTMLMediaElement.prototype);

  useEffect(() => {
    const el = audio.current;
    if (!el) return;
    const el2 = el as HTMLAudioElement & { preservesPitch?: boolean; webkitPreservesPitch?: boolean };
    el2.preservesPitch = true;
    el2.webkitPreservesPitch = true;
    el.playbackRate = canKeepPitch ? rate : 1;
  }, [rate, canKeepPitch]);

  useEffect(() => {
    let raf = 0;
    const step = () => {
      const el = audio.current;
      if (el) {
        if (a !== null && b !== null && b > a && el.currentTime >= b) el.currentTime = a;
        setPos(el.currentTime);
        setPlaying(!el.paused);
      }
      raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [a, b]);

  if (!track) return <p className="error">Recording missing.</p>;
  const el = () => audio.current!;

  return (
    <div className="stack player">
      {!embedded && <h1>{detail.title}</h1>}
      <p className="tag">Recording and PDF. Repeats are set by time, not by bar.</p>
      {detail.manual?.note && <p className="muted">{detail.manual.note}</p>}
      <audio ref={audio} src={assetUrl(track.id)} preload="metadata" onLoadedMetadata={(e) => setDur(e.currentTarget.duration)} />
      <div className="barnow">{formatTime(pos)} / {formatTime(dur)}</div>
      <input type="range" aria-label="Position" min={0} max={dur || 0} step={0.1} value={pos}
        onChange={(e) => (el().currentTime = Number(e.target.value))} />
      <div className="row">
        <button className="big" onClick={() => (el().currentTime = a ?? 0)}>⏮</button>
        <button className="big primary grow" onClick={() => (playing ? el().pause() : void el().play())}>
          {playing ? "Pause" : "Play"}
        </button>
      </div>
      <section>
        <h2 className="label">Repeat a passage</h2>
        <div className="row wrap">
          <button onClick={() => setA(el().currentTime)}>Start here{a !== null && ` (${formatTime(a)})`}</button>
          <button onClick={() => setB(el().currentTime)}>End here{b !== null && ` (${formatTime(b)})`}</button>
          <button onClick={() => { setA(null); setB(null); }}>Clear</button>
        </div>
        {a !== null && b !== null && b <= a && <p className="error">The end must be after the start.</p>}
      </section>
      <section>
        <h2 className="label">Speed</h2>
        {canKeepPitch ? (
          <div className="seg">
            {[1, 0.75, 0.5].map((r) => (
              <button key={r} className={r === rate ? "on" : ""} onClick={() => setRate(r)}>
                {r === 1 ? "Normal" : `${r * 100}%`}
              </button>
            ))}
          </div>
        ) : (
          <p className="muted">This browser cannot slow a recording without changing its pitch, so slow practice is off.</p>
        )}
        <p className="muted small">Slowed recordings use the browser's time-stretch; quality varies by phone.</p>
      </section>
      {pdf && (
        <a className="button big" href={assetUrl(pdf.id)} target="_blank" rel="noopener">
          Open the score (PDF)
        </a>
      )}
    </div>
  );
}
