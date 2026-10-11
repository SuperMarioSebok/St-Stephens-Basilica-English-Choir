import { useEffect, useState } from "react";
import { go } from "../App";
import { get, PART_NAMES, PARTS, post, type Me, type Part, type VersionDetail } from "../lib/api";
import { draftFrom, entryFrom, MappingFields, type Draft } from "./MappingEditor";
import Player from "./Player";
import VideoList from "./VideoList";

export default function Review({ versionId, me }: { versionId: number; me: Me }) {
  const [d, setD] = useState<VersionDetail | null>(null);
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");
  const [note, setNote] = useState("");
  const [drafts, setDrafts] = useState<Record<Part, Draft> | null>(null);

  const load = () =>
    get<VersionDetail>(`/api/versions/${versionId}`)
      .then((v) => {
        setD(v);
        if (v.mapping) setDrafts(Object.fromEntries(PARTS.map((p) => [p, draftFrom(v.mapping![p])])) as Record<Part, Draft>);
      })
      .catch((e) => setError(e.message));
  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [versionId]);

  if (error) return <p className="error">{error}</p>;
  if (!d) return <p>Loading…</p>;
  const director = me.role === "director";
  const act = (p: Promise<unknown>, after?: () => void) =>
    p.then(() => (after ? after() : load())).catch((e) => setMsg(e.message));
  const rendered = d.render?.status === "done";
  const flags = d.model?.flags ?? [];

  async function confirmAll() {
    setMsg("");
    try {
      const entries = Object.fromEntries(PARTS.map((p) => [p, entryFrom(drafts![p], d!.inventory!.streams)]));
      const r = await post<{ version_id: number }>(`/api/versions/${versionId}/mapping`, { entries, confirm: true });
      go(`/review/${r.version_id}`);
    } catch (e) {
      setMsg((e as Error).message);
    }
  }

  return (
    <div className="stack">
      <h1>{d.title}</h1>
      <p>
        Version {d.number} · <strong>{d.status}</strong> · {d.change_summary}
        {!d.latest && <span className="warn"> · not the latest version</span>}
      </p>
      {d.review_decision_note && <p className="notice">Director's note: {d.review_decision_note}</p>}

      <section className="card">
        <h2>Audio</h2>
        <p>
          Status: {d.render?.status}
          {d.render?.attempts ? ` (attempt ${d.render.attempts} of ${d.render.max_attempts})` : ""}
          {d.render?.error ? ` · ${d.render.error}` : ""}
        </p>
        <div className="row wrap">
          <button onClick={() => void load()}>Refresh</button>
          {director && d.kind === "score" && d.render?.status === "failed" && (
            <button onClick={() => act(post(`/api/versions/${versionId}/rerender`))}>Try rendering again</button>
          )}
        </div>
      </section>

      {d.kind === "score" && d.inventory && drafts && (
        <section className="card">
          <h2>Part mapping</h2>
          <p className="small muted">
            Proposed from part names. Nothing reaches singers until each part is confirmed by a person.
          </p>
          {PARTS.map((p) => (
            <div key={p} className="mapping-row">
              <p>
                <strong>{PART_NAMES[p]}</strong>{" "}
                {d.mapping?.[p]?.confirmed ? <span className="ok">confirmed by {d.mapping[p].confirmed_by}</span> : <span className="warn">not confirmed</span>}
              </p>
              <MappingFields part={p} draft={drafts[p]} streams={d.inventory!.streams} disabled={!director || !d.latest}
                onChange={(x) => setDrafts({ ...drafts, [p]: x })} />
            </div>
          ))}
          {director && d.latest && <button className="primary" onClick={confirmAll}>Confirm all four as shown</button>}
        </section>
      )}

      {flags.length > 0 && (
        <section className="card">
          <h2>Things to check</h2>
          <ul className="flags">
            {flags.map((f, i) => (
              <li key={i} className={f.level}>
                {f.part ? `${PART_NAMES[f.part]}: ` : ""}{f.message}
              </li>
            ))}
          </ul>
        </section>
      )}

      {rendered && (
        <section className="card">
          <h2>Listen before deciding</h2>
          <Player versionId={versionId} me={me} embedded />
        </section>
      )}

      {d.kind === "score" && rendered && (
        <section className="card">
          <h2>Practice videos</h2>
          <p className="small muted">Private videos for each part (alone, louder, full choir) at 100% and 75% speed, with the bar number on screen. Singers see them once this version is approved. Nothing is uploaded anywhere.</p>
          <p>Status: {d.videos?.status === "none" ? "not made yet" : d.videos?.status}{d.videos?.error ? ` · ${d.videos.error}` : ""}</p>
          <div className="row wrap">
            {director && d.videos?.status !== "queued" && d.videos?.status !== "running" && (
              <button onClick={() => act(post(`/api/versions/${versionId}/videos`))}>
                {d.videos?.status === "done" ? "Make videos again" : "Make practice videos"}
              </button>
            )}
            <button onClick={() => void load()}>Refresh</button>
          </div>
          <VideoList assets={d.assets} />
        </section>
      )}

      <section className="card">
        <h2>Decision</h2>
        {d.readiness && d.readiness.length > 0 && (
          <ul className="flags">{d.readiness.map((r, i) => <li key={i} className="warn">{r}</li>)}</ul>
        )}
        <div className="row wrap">
          {me.role === "voice_lead" && d.kind === "score" && <a className="button" href={`#/edit/${versionId}`}>Edit my part</a>}
          <a className="button" href={`#/history/${d.song_id}`}>History and notes</a>
          {d.latest && (d.status === "draft" || d.status === "rejected") && (
            <button onClick={() => act(post(`/api/versions/${versionId}/submit`))}>Submit for review</button>
          )}
        </div>
        {director && d.status === "in_review" && (
          <div className="stack tight">
            <textarea placeholder="Note to the voice leads (optional)" value={note} maxLength={1000} onChange={(e) => setNote(e.target.value)} />
            <div className="row">
              <button className="big primary grow" onClick={() => act(post(`/api/versions/${versionId}/approve`, { note }))}>
                Approve for singers
              </button>
              <button className="big grow" onClick={() => act(post(`/api/versions/${versionId}/reject`, { note }))}>
                Request changes
              </button>
            </div>
          </div>
        )}
      </section>
      {msg && <p className="error" role="status">{msg}</p>}
    </div>
  );
}
