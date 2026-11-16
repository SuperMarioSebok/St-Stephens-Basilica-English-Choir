import { useCallback, useEffect, useState, type FormEvent } from "react";
import { get, post, PART_NAMES, type Dashboard as Data, type KbHit, type Me, type Rehearsal } from "../lib/api";

const dayFmt = new Intl.DateTimeFormat("en-GB", { weekday: "short", day: "numeric", month: "short", timeZone: "UTC" });
const formatDay = (iso: string) => dayFmt.format(new Date(`${iso}T00:00:00Z`));

function rehearsalTime(r: Rehearsal): string {
  if (!r.start_time) return "time to be confirmed";
  return r.end_time ? `${r.start_time}–${r.end_time}` : `from ${r.start_time}`;
}

// The server marks matched words as [[word]]; render them without injecting HTML.
function Snippet({ text }: { text: string }) {
  return (
    <>
      {text.split(/\[\[|\]\]/).map((piece, i) => (i % 2 ? <mark key={i}>{piece}</mark> : <span key={i}>{piece}</span>))}
    </>
  );
}

export default function Dashboard({ me }: { me: Me }) {
  const [data, setData] = useState<Data | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    get<Data>("/api/dashboard").then(setData).catch((e) => setError(e.message));
  }, []);
  useEffect(load, [load]);

  if (error && !data) return <p className="error">{error}</p>;
  if (!data) return <p>Loading…</p>;

  const total = data.songs.length * data.stages.length;
  const done = data.songs.reduce((sum, s) => sum + s.stage, 0);
  const ready = data.songs.filter((s) => s.stage === data.stages.length).length;

  const setStage = (songId: number, stage: number) => {
    // Tapping the current stage again steps back one, so a mis-tap can be undone.
    const current = data.songs.find((s) => s.id === songId)?.stage ?? 0;
    const next = current === stage ? stage - 1 : stage;
    setData({ ...data, songs: data.songs.map((s) => (s.id === songId ? { ...s, stage: next } : s)) });
    post<{ stage: number; streak: number }>("/api/practice", { repertoire_id: songId, stage: next })
      .then((r) => setData((d) => d && { ...d, streak: r.streak }))
      .catch((e) => { setError(e.message); load(); });
  };

  const rsvp = (id: number, answer: "yes" | "no") => {
    setData({ ...data, rehearsals: data.rehearsals.map((r) => (r.id === id ? { ...r, my_rsvp: answer } : r)) });
    post(`/api/rehearsals/${id}/rsvp`, { rsvp: answer }).catch((e) => { setError(e.message); load(); });
  };

  return (
    <div className="stack">
      {data.notices.map((n) => (
        <p key={n.id} className={n.level === "urgent" ? "alert" : "notice"} role={n.level === "urgent" ? "alert" : undefined}>
          {n.level === "urgent" && <strong>Schedule change. </strong>}
          {n.text}
        </p>
      ))}

      <section>
        <h1>{data.concert.days_left > 0 ? `${data.concert.days_left} days to the concert` : "Concert day"}</h1>
        <p className="muted">
          {data.concert.title} · {formatDay(data.concert.date)}
          {me.voice_part && ` · ${PART_NAMES[me.voice_part]}`}
        </p>
      </section>
      {error && <p className="error">{error}</p>}

      <section className="stack tight">
        <h2 className="label">Rehearsals remaining ({data.rehearsals.length})</h2>
        {data.rehearsals.length === 0 && <p className="muted">No rehearsals left before the concert.</p>}
        <ul className="cards">
          {data.rehearsals.map((r) => (
            <li key={r.id} className="card rehearsal">
              <div className="grow">
                <strong>{formatDay(r.day)}</strong>
                {r.kind !== "weekend" && <span className="tag new">{r.kind === "thursday" ? "New Thursday" : "Extra"}</span>}
                <div className="muted small">{rehearsalTime(r)}{r.note ? ` · ${r.note}` : ""}</div>
              </div>
              <div className="row">
                <button className={r.my_rsvp === "yes" ? "on" : ""} aria-pressed={r.my_rsvp === "yes"} onClick={() => rsvp(r.id, "yes")}>
                  I'm coming
                </button>
                <button className={r.my_rsvp === "no" ? "on" : ""} aria-pressed={r.my_rsvp === "no"} onClick={() => rsvp(r.id, "no")}>
                  Can't
                </button>
              </div>
            </li>
          ))}
        </ul>
      </section>

      <section className="stack tight">
        <h2 className="label">My practice checklist</h2>
        <div className="card">
          <div className="row wrap stats">
            <span><strong>{ready}</strong> of {data.songs.length} songs ready</span>
            <span><strong>{data.streak}</strong> day streak</span>
          </div>
          <progress value={done} max={total} aria-label="Overall practice progress" />
          <p className="muted small">Tap the stage you have reached for each song. Only you can see this.</p>
        </div>
        <ol className="cards">
          {data.songs.map((s) => (
            <li key={s.id} className="card">
              <div className="row">
                <h2 className="grow">{s.position}. {s.title}</h2>
                {s.practise_version_id && <a className="button" href={`#/plan/${s.practise_version_id}/play`}>Plan</a>}
                {s.practise_version_id && <a className="button primary" href={`#/play/${s.practise_version_id}`}>Practise</a>}
              </div>
              <div className="stages">
                {data.stages.map((label, i) => (
                  <button key={label} className={s.stage > i ? "on" : ""} aria-pressed={s.stage > i} onClick={() => setStage(s.id, i + 1)}>
                    <span className="num">{s.stage > i ? "✓" : i + 1}</span> {label}
                  </button>
                ))}
              </div>
            </li>
          ))}
        </ol>
      </section>

      <KnowledgeSearch />
    </div>
  );
}

function KnowledgeSearch() {
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<KbHit[] | null>(null);
  const [error, setError] = useState("");

  const search = (e: FormEvent) => {
    e.preventDefault();
    if (!q.trim()) return;
    setError("");
    get<KbHit[]>(`/api/kb/search?q=${encodeURIComponent(q)}`).then(setHits).catch((err) => setError(err.message));
  };

  return (
    <section className="stack tight">
      <h2 className="label">Ask the choir handbook</h2>
      <form className="row" onSubmit={search} role="search">
        <input
          className="grow" type="search" value={q} maxLength={200} aria-label="Search choir documents"
          placeholder="e.g. dress code, how to log practice" onChange={(e) => setQ(e.target.value)}
        />
        <button className="primary" type="submit">Search</button>
      </form>
      {error && <p className="error">{error}</p>}
      {hits && hits.length === 0 && <p className="muted">Nothing found. Try other words, or ask your section lead.</p>}
      {hits && hits.length > 0 && (
        <ul className="cards">
          {hits.map((h, i) => (
            <li key={i} className="card">
              <p className="small muted">{h.title}{h.heading ? ` › ${h.heading}` : ""}</p>
              <p><Snippet text={h.snippet} /></p>
              {h.url && <a href={h.url} target="_blank" rel="noreferrer">Open the document</a>}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
