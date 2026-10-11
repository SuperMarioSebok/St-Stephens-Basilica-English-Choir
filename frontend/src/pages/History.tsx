import { useEffect, useState } from "react";
import { get, PART_NAMES, type Part } from "../lib/api";

interface Change {
  at: string;
  action: string;
  part: Part | null;
  who: string;
  version: number;
  detail: Record<string, unknown>;
}
interface Note {
  at: string;
  part: Part | null;
  bar_index: number | null;
  text: string;
  who: string;
  version: number;
}

const ACTIONS: Record<string, string> = {
  import: "Imported score",
  "manual-upload": "Uploaded recording",
  mapping: "Mapping",
  "edit-notes": "Edited notes",
  label: "Changed label",
  reupload: "Uploaded correction",
  submit: "Submitted for review",
  approve: "Approved",
  reject: "Requested changes",
};

function describe(c: Change): string {
  const d = c.detail as Record<string, unknown>;
  if (c.action === "edit-notes")
    return (d.bars as { bar: string; before: string; after: string }[])
      .map((b) => `bar ${b.bar}: ${b.before} → ${b.after}`)
      .join("; ");
  if (c.action === "mapping") return `${d.before ?? "none"} → ${d.after ?? "none"}${d.octave_shift ? `, octave ${d.octave_shift}` : ""}`;
  if (c.action === "label") return `${d.before} → ${d.after}`;
  if (c.action === "reupload") return `bars changed: ${(d.bars_changed as string[]).join(", ") || "none"}`;
  if (c.action === "approve" || c.action === "reject") return (d.note as string) || "";
  return "";
}

export default function History({ songId }: { songId: number }) {
  const [data, setData] = useState<{ changes: Change[]; notes: Note[] } | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    get<{ changes: Change[]; notes: Note[] }>(`/api/songs/${songId}/history`).then(setData).catch((e) => setError(e.message));
  }, [songId]);
  if (error) return <p className="error">{error}</p>;
  if (!data) return <p>Loading…</p>;
  return (
    <div className="stack">
      <h1>History</h1>
      <ul className="history">
        {data.changes.map((c, i) => (
          <li key={i}>
            <strong>v{c.version}</strong> · {new Date(c.at).toLocaleString("en-GB", { timeZone: "Europe/Budapest" })} · {c.who}
            <br />
            {ACTIONS[c.action] ?? c.action}
            {c.part ? ` (${PART_NAMES[c.part]})` : ""} <span className="muted">{describe(c)}</span>
          </li>
        ))}
      </ul>
      <h2>Review notes</h2>
      {data.notes.length === 0 && <p className="muted">No notes yet.</p>}
      <ul className="history">
        {data.notes.map((n, i) => (
          <li key={i}>
            <strong>v{n.version}</strong> · {n.who}
            {n.part ? ` · ${PART_NAMES[n.part]}` : ""}
            {n.bar_index !== null ? ` · bar index ${n.bar_index}` : ""}
            <br />
            {n.text}
          </li>
        ))}
      </ul>
    </div>
  );
}
