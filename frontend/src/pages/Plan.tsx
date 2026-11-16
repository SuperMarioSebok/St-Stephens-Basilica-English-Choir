import { useEffect, useState } from "react";
import { get, PARTS, PART_NAMES, type Me, type Part, type PracticePlan, type PlanStep } from "../lib/api";

const dayFmt = new Intl.DateTimeFormat("en-GB", { weekday: "short", day: "numeric", month: "short", timeZone: "UTC" });
const formatDay = (iso: string) => dayFmt.format(new Date(`${iso}T00:00:00Z`));
const MINUTES = [5, 15, 30];

function playerLink(versionId: number, part: Part, step: PlanStep): string {
  const q = new URLSearchParams({ part });
  if (step.from_index !== undefined && step.to_index !== undefined) {
    q.set("from", String(step.from_index));
    q.set("to", String(step.to_index));
  }
  if (step.tempo) q.set("tempo", String(step.tempo));
  return `#/play/${versionId}?${q}`;
}

export default function Plan({ versionId, me, canPlay }: { versionId: number; me: Me; canPlay?: boolean }) {
  const [part, setPart] = useState<Part>(me.voice_part ?? "T");
  const [minutes, setMinutes] = useState(15);
  const [plan, setPlan] = useState<PracticePlan | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    setError("");
    get<PracticePlan>(`/api/versions/${versionId}/plan?part=${part}&minutes=${minutes}`)
      .then(setPlan)
      .catch((e) => setError(e.message));
  }, [versionId, part, minutes]);

  if (error) return <p className="error">{error}</p>;
  if (!plan) return <p>Reading the score…</p>;
  const inPiece = plan.overview.map((o) => o.part);

  return (
    <div className="stack">
      <section>
        <h1>Practice plan</h1>
        <p className="muted">{plan.title} · worked out from the score</p>
      </section>

      <div className="seg" role="group" aria-label="Voice part">
        {PARTS.filter((p) => inPiece.includes(p)).map((p) => (
          <button key={p} className={p === part ? "on" : ""} aria-pressed={p === part} onClick={() => setPart(p)}>
            {PART_NAMES[p]}
          </button>
        ))}
      </div>

      {!plan.in_piece || !plan.summary || !plan.schedule ? (
        <p className="notice">{PART_NAMES[part]} does not sing in this piece.</p>
      ) : (
        <>
          <section className="card stack tight">
            <div className="row wrap stats">
              <span><strong>{plan.summary.rating}</strong></span>
              <span>range {plan.summary.range}</span>
              <span>{plan.summary.sounding_bars} bars to sing</span>
            </div>
            <div className="row wrap">
              <span className="small muted">Minutes a day:</span>
              {MINUTES.map((m) => (
                <button key={m} className={m === minutes ? "on" : ""} aria-pressed={m === minutes} onClick={() => setMinutes(m)}>{m}</button>
              ))}
            </div>
            {plan.schedule.tight && (
              <p className="warn">
                Only {plan.schedule.days_available} practice day{plan.schedule.days_available === 1 ? "" : "s"} left, so
                this plan needs {plan.schedule.sessions_per_day} sessions a day.
              </p>
            )}
          </section>

          <section className="stack tight">
            <h2 className="label">Tricky bars ({plan.hot_spots.length})</h2>
            {plan.hot_spots.length === 0 && <p className="muted">No bar stands out as hard for this part.</p>}
            <ul className="cards">
              {plan.hot_spots.map((s) => (
                <li key={s.from_index} className="card rehearsal">
                  <div className="grow">
                    <strong>Bar {s.from_label}{s.to_label !== s.from_label ? `–${s.to_label}` : ""}</strong>
                    <div className="muted small">{s.reasons.join(", ")}</div>
                  </div>
                  {canPlay && <a className="button" href={playerLink(versionId, part, s)}>Loop at {s.tempo}%</a>}
                </li>
              ))}
            </ul>
          </section>

          <section className="stack tight">
            <h2 className="label">Day by day</h2>
            <ol className="cards">
              {plan.sessions.map((s, i) => (
                <li key={i} className="card">
                  <p className="small muted">{formatDay(s.day)} · about {s.minutes} min · stage {s.stage}</p>
                  <h2>{s.title}</h2>
                  <ul className="steps">
                    {s.steps.map((st, j) => (
                      <li key={j}>
                        {st.text}{" "}
                        {canPlay && st.kind !== "record" && <a href={playerLink(versionId, part, st)}>Open in player</a>}
                      </li>
                    ))}
                  </ul>
                </li>
              ))}
            </ol>
          </section>

          {me.role !== "singer" && (
            <section className="stack tight">
              <h2 className="label">All parts (for rehearsal planning)</h2>
              <table className="overview">
                <thead><tr><th>Part</th><th>Level</th><th>Tricky bars</th><th>Range</th></tr></thead>
                <tbody>
                  {plan.overview.map((o) => (
                    <tr key={o.part}><td>{PART_NAMES[o.part]}</td><td>{o.rating}</td><td>{o.tricky_bars}</td><td>{o.range}</td></tr>
                  ))}
                </tbody>
              </table>
            </section>
          )}
        </>
      )}
    </div>
  );
}
