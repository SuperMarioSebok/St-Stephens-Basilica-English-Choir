import { useState } from "react";
import { PART_NAMES, post, type MappingEntry, type Part, type Stream } from "../lib/api";

const midiName = (m: number | null) => {
  if (m === null) return "?";
  const n = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"][m % 12];
  return `${n}${Math.floor(m / 12) - 1}`;
};

export function streamLabel(s: Stream) {
  return `${s.part_name} · staff ${s.staff} · voice ${s.voice} · ${s.note_count} notes, ${midiName(s.low)}–${midiName(s.high)}${s.chord_count ? ` · ${s.chord_count} chords` : ""}`;
}

export interface Draft {
  key: string; // stream key or "none"
  octave: number;
}

export function draftFrom(m: MappingEntry | undefined): Draft {
  if (!m || !m.part_id) return { key: m?.confirmed ? "none" : "", octave: 0 };
  return { key: `${m.part_id}/${m.staff}/${m.voice}`, octave: m.octave_shift };
}

export function entryFrom(d: Draft, streams: Stream[]) {
  if (d.key === "none") return { none: true };
  const s = streams.find((x) => x.key === d.key);
  if (!s) throw new Error("Choose where this part is in the score");
  return { part_id: s.part_id, staff: s.staff, voice: s.voice, octave_shift: d.octave };
}

export function MappingFields({
  part, draft, streams, onChange, disabled,
}: { part: Part; draft: Draft; streams: Stream[]; onChange: (d: Draft) => void; disabled?: boolean }) {
  return (
    <div className="stack tight">
      <label>
        {PART_NAMES[part]} is sung from
        <select disabled={disabled} value={draft.key} onChange={(e) => onChange({ ...draft, key: e.target.value })}>
          <option value="">Choose…</option>
          {streams.map((s) => <option key={s.key} value={s.key}>{streamLabel(s)}</option>)}
          <option value="none">This piece has no {PART_NAMES[part]} part</option>
        </select>
      </label>
      {draft.key !== "none" && (
        <label>
          Octave
          <select disabled={disabled} value={draft.octave} onChange={(e) => onChange({ ...draft, octave: Number(e.target.value) })}>
            <option value={-1}>Sing one octave lower than written (e.g. tenor in plain treble clef)</option>
            <option value={0}>As written</option>
            <option value={1}>One octave higher than written</option>
          </select>
        </label>
      )}
    </div>
  );
}

/** One part's mapping with a confirm button (Voice Lead: own part). */
export function SinglePartMapping({
  versionId, part, mapping, streams, onSaved,
}: { versionId: number; part: Part; mapping?: MappingEntry; streams: Stream[]; onSaved: (vid: number) => void }) {
  const [draft, setDraft] = useState(draftFrom(mapping));
  const [error, setError] = useState("");
  async function save() {
    setError("");
    try {
      const r = await post<{ version_id: number }>(`/api/versions/${versionId}/mapping`, {
        entries: { [part]: entryFrom(draft, streams) },
        confirm: true,
      });
      onSaved(r.version_id);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  return (
    <div className="stack tight">
      <p>
        Status:{" "}
        {mapping?.confirmed ? <span className="ok">confirmed by {mapping.confirmed_by}</span> : <span className="warn">not confirmed</span>}
      </p>
      <MappingFields part={part} draft={draft} streams={streams} onChange={setDraft} />
      {error && <p className="error">{error}</p>}
      <button className="primary" onClick={save}>Confirm this mapping</button>
    </div>
  );
}
