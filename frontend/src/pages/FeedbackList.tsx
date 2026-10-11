import { useEffect, useState } from "react";
import { get } from "../lib/api";

interface Row {
  song: string;
  bar_label: string | null;
  comment: string;
  week: string;
}

export default function FeedbackList() {
  const [rows, setRows] = useState<Row[] | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    get<Row[]>("/api/feedback").then(setRows).catch((e) => setError(e.message));
  }, []);
  if (error) return <p className="error">{error}</p>;
  if (!rows) return <p>Loading…</p>;
  const weeks = [...new Set(rows.map((r) => r.week))];
  return (
    <div className="stack">
      <h1>Singer feedback</h1>
      <p className="muted small">
        Shown by week only, in random order within a week. No names or exact times are stored. Please do not try to
        work out who wrote a note.
      </p>
      {rows.length === 0 && <p className="muted">No feedback yet.</p>}
      {weeks.map((w) => (
        <section key={w}>
          <h2>Week {w}</h2>
          <ul className="cards">
            {rows.filter((r) => r.week === w).map((r, i) => (
              <li key={i} className="card">
                <p className="muted small">{r.song}{r.bar_label ? ` · bar ${r.bar_label}` : ""}</p>
                <p>{r.comment}</p>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
