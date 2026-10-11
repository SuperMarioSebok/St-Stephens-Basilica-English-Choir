import { useEffect, useMemo, useState } from "react";
import { go } from "../App";
import { get, PART_NAMES, PARTS, post, postForm, type Me, type Part, type VersionDetail } from "../lib/api";
import { barQuarters, parseBar, playBars, stopPreview, type PNote } from "../lib/synth";
import { SinglePartMapping } from "./MappingEditor";

const TPQ = 480;

export default function Editor({ versionId, me }: { versionId: number; me: Me }) {
  const [d, setD] = useState<VersionDetail | null>(null);
  const [error, setError] = useState("");
  const [part, setPart] = useState<Part>(me.voice_part ?? "T");
  const [drafts, setDrafts] = useState<Record<number, string>>({});
  const [summary, setSummary] = useState("");
  const [msg, setMsg] = useState("");
  const [range, setRange] = useState<[number, number]>([1, 2]);
  const [label, setLabel] = useState("");
  const [noteBar, setNoteBar] = useState<number | "">("");
  const [noteText, setNoteText] = useState("");

  useEffect(() => {
    setDrafts({});
    get<VersionDetail>(`/api/versions/${versionId}`).then((v) => {
      setD(v);
      setLabel(v.mapping?.[part]?.label ?? PART_NAMES[part]);
    }).catch((e) => setError(e.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [versionId]);

  const before = d?.bar_tokens?.[part] ?? null;
  const bars = d?.model?.bars ?? [];
  const bpm = d?.model?.tempo[0]?.bpm ?? 80;
  const textAt = (i: number) => drafts[i] ?? before?.[i] ?? "";
  const check = (i: number): string | null => {
    const { notes, error } = parseBar(textAt(i));
    if (error) return error;
    const want = bars[i].ticks / TPQ;
    const got = barQuarters(notes);
    return Math.abs(got - want) > 1e-6 ? `Adds up to ${got} beats; this bar needs ${want}` : null;
  };
  const changed = useMemo(
    () => Object.keys(drafts).map(Number).filter((i) => before && drafts[i].trim() !== before[i]),
    [drafts, before],
  );

  if (error) return <p className="error">{error}</p>;
  if (!d) return <p>Loading…</p>;
  if (d.kind !== "score") return <p>This song is a recording; it has no editable parts.</p>;
  const canEdit = me.role === "director" || me.voice_part === part;
  const flags = (d.model?.flags ?? []).filter((f) => f.part === part);
  const reload = (vid: number) => go(`/edit/${vid}`);

  async function play(which: "before" | "after" | "both", from: number, to: number) {
    const pick = (src: (i: number) => string) => {
      const out: PNote[][] = [];
      for (let i = from; i <= to; i++) out.push(parseBar(src(i)).notes);
      return out;
    };
    const orig = pick((i) => before?.[i] ?? "");
    const edit = pick(textAt);
    if (which === "before") await playBars(orig, bpm);
    else if (which === "after") await playBars(edit, bpm);
    else {
      const len = await playBars(orig, bpm, 0.8);
      window.setTimeout(() => void playBars(edit, bpm), len * 1000);
    }
  }

  async function save() {
    setMsg("");
    const bad = changed.map((i) => [i, check(i)] as const).filter(([, e]) => e);
    if (bad.length) return setMsg(`Fix bar ${bars[bad[0][0]].label}: ${bad[0][1]}`);
    try {
      const body = { bars: Object.fromEntries(changed.map((i) => [String(i), drafts[i].trim()])), summary };
      const r = await post<{ version_id: number }>(`/api/versions/${versionId}/parts/${part}/bars`, body);
      reload(r.version_id);
    } catch (e) {
      setMsg((e as Error).message);
    }
  }

  async function reupload(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setMsg("");
    try {
      const r = await postForm<{ version_id: number }>(`/api/versions/${versionId}/parts/${part}/reupload`, new FormData(e.currentTarget));
      reload(r.version_id);
    } catch (err) {
      setMsg((err as Error).message);
    }
  }

  return (
    <div className="stack">
      <h1>{d.title}</h1>
      <p className="muted">
        Version {d.number} · {d.status} {d.latest ? "" : "· a newer version exists, go back to Songs"}
      </p>
      {me.role === "director" && (
        <div className="seg">
          {PARTS.map((p) => <button key={p} className={p === part ? "on" : ""} onClick={() => { setPart(p); setDrafts({}); }}>{PART_NAMES[p]}</button>)}
        </div>
      )}
      <p className="notice">
        Every saved change creates a new version, cancels the current approval and regenerates the audio. Singers keep
        seeing nothing new until the director approves.
      </p>

      <section className="card">
        <h2>1. Where is {PART_NAMES[part]} in the score?</h2>
        {d.inventory && d.latest && canEdit && (
          <SinglePartMapping versionId={versionId} part={part} mapping={d.mapping?.[part]} streams={d.inventory.streams} onSaved={reload} />
        )}
        {flags.length > 0 && (
          <ul className="flags">
            {flags.map((f, i) => <li key={i} className={f.level}>{f.message}</li>)}
          </ul>
        )}
      </section>

      <section className="card">
        <h2>2. Part label</h2>
        <div className="row">
          <input value={label} maxLength={40} onChange={(e) => setLabel(e.target.value)} />
          <button disabled={!canEdit || !d.latest} onClick={() =>
            post<{ version_id: number }>(`/api/versions/${versionId}/parts/${part}/label`, { label }).then((r) => reload(r.version_id)).catch((e) => setMsg(e.message))
          }>Save label</button>
        </div>
      </section>

      <section className="card">
        <h2>3. Notes, bar by bar</h2>
        {!before ? (
          <p className="muted">Map this part first.</p>
        ) : (
          <>
            <details>
              <summary>How to write notes</summary>
              <p className="small">
                Pitch and length in beats, separated by spaces. <code>G4:1</code> quarter note G4,{" "}
                <code>F#3:0.5</code> eighth note, <code>Bb3:1.5</code> dotted quarter, <code>R:2</code> half rest,{" "}
                <code>C4+E4:1</code> two notes at once (divisi), <code>D4:2~</code> tied into the next note.
                Middle C is C4. Tenor is written at sounding pitch (tenor middle C is C4).
              </p>
            </details>
            <div className="row wrap compare">
              <label className="inline">Compare bars
                <select value={range[0]} onChange={(e) => setRange([Number(e.target.value), range[1]])}>
                  {bars.map((b) => <option key={b.index} value={b.index}>{b.label}</option>)}
                </select>
              </label>
              <label className="inline">to
                <select value={range[1]} onChange={(e) => setRange([range[0], Number(e.target.value)])}>
                  {bars.map((b) => <option key={b.index} value={b.index}>{b.label}</option>)}
                </select>
              </label>
              <button onClick={() => void play("before", Math.min(...range), Math.max(...range))}>▶ Original</button>
              <button onClick={() => void play("after", Math.min(...range), Math.max(...range))}>▶ My edit</button>
              <button onClick={() => void play("both", Math.min(...range), Math.max(...range))}>▶ Original, then edit</button>
              <button onClick={stopPreview}>■</button>
            </div>
            <p className="muted small">Preview uses a simple tone at {bpm} BPM. The practice audio is rendered after saving.</p>
            <table className="bars-edit">
              <thead><tr><th>Bar</th><th>Original (v{d.number})</th><th>Your edit</th><th /></tr></thead>
              <tbody>
                {bars.map((b, i) => {
                  const err = drafts[i] !== undefined ? check(i) : null;
                  const isChanged = changed.includes(i);
                  return (
                    <tr key={i} className={isChanged ? "changed" : ""}>
                      <td>{b.label}</td>
                      <td><code>{before[i]}</code></td>
                      <td>
                        <input
                          disabled={!canEdit || !d.latest}
                          value={textAt(i)}
                          spellCheck={false}
                          autoCapitalize="characters"
                          onChange={(e) => setDrafts({ ...drafts, [i]: e.target.value })}
                          aria-invalid={!!err}
                        />
                        {err && <div className="error small">{err}</div>}
                      </td>
                      <td className="nowrap">
                        <button aria-label={`Play original bar ${b.label}`} onClick={() => void play("before", i, i)}>▶ Before</button>
                        <button aria-label={`Play edited bar ${b.label}`} onClick={() => void play("after", i, i)}>▶ After</button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            <label>
              What did you change and why? (shown in history)
              <input value={summary} maxLength={300} onChange={(e) => setSummary(e.target.value)} />
            </label>
            <button className="big primary" disabled={!changed.length || !canEdit || !d.latest} onClick={save}>
              Save {changed.length || ""} changed bar{changed.length === 1 ? "" : "s"} as a new version
            </button>
          </>
        )}
      </section>

      <section className="card">
        <h2>4. Or upload a corrected MusicXML</h2>
        <p className="small muted">
          Only the {PART_NAMES[part]} part is taken from the file; everything else in it is ignored. The bar structure
          must match the current version.
        </p>
        <form onSubmit={reupload} className="stack tight">
          <input type="file" name="score" accept=".musicxml,.xml,.mxl" required />
          <button disabled={!canEdit || !d.latest}>Upload correction</button>
        </form>
      </section>

      <section className="card">
        <h2>5. Review note</h2>
        <div className="stack tight">
          <select value={noteBar} onChange={(e) => setNoteBar(e.target.value === "" ? "" : Number(e.target.value))}>
            <option value="">Whole piece</option>
            {bars.map((b) => <option key={b.index} value={b.index}>Bar {b.label}</option>)}
          </select>
          <textarea value={noteText} maxLength={2000} onChange={(e) => setNoteText(e.target.value)} placeholder="For example: bar 5, check the rhythm against the printed copy" />
          <button onClick={() =>
            post(`/api/versions/${versionId}/notes`, { part, bar_index: noteBar === "" ? null : noteBar, text: noteText })
              .then(() => { setNoteText(""); setMsg("Note saved."); }).catch((e) => setMsg(e.message))
          }>Add note</button>
        </div>
      </section>

      <section className="card">
        <h2>6. Send to the director</h2>
        {d.readiness && d.readiness.length > 0 && (
          <ul className="flags">{d.readiness.map((r, i) => <li key={i} className="warn">{r}</li>)}</ul>
        )}
        <p className="muted small">Audio: {d.render?.status}{d.render?.error ? ` (${d.render.error})` : ""}. Reload the page to refresh.</p>
        <button className="big" disabled={!d.latest || d.status === "in_review"} onClick={() =>
          post(`/api/versions/${versionId}/submit`).then(() => go(`/review/${versionId}`)).catch((e) => setMsg(e.message))
        }>Submit for review</button>
      </section>
      {msg && <p className="error" role="status">{msg}</p>}
    </div>
  );
}
