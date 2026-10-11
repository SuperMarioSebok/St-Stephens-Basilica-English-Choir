import { useEffect, useState } from "react";
import { get, post, type SongItem, type VersionDetail } from "../lib/api";
import { barName } from "../lib/timeline";

export default function Feedback({ songId }: { songId?: number }) {
  const [songs, setSongs] = useState<SongItem[]>([]);
  const [song, setSong] = useState<number | "">(songId ?? "");
  const [bars, setBars] = useState<VersionDetail["timeline"] | null>(null);
  const [bar, setBar] = useState(new URLSearchParams(window.location.hash.split("?")[1] ?? "").get("bar") ?? "");
  const [comment, setComment] = useState("");
  const [state, setState] = useState<"" | "sending" | "sent">("");
  const [error, setError] = useState("");

  useEffect(() => {
    get<SongItem[]>("/api/songs").then((s) => setSongs(s.filter((x) => x.approved_version_id)));
  }, []);
  useEffect(() => {
    const s = songs.find((x) => x.id === song);
    if (!s?.approved_version_id) return setBars(null);
    get<VersionDetail>(`/api/versions/${s.approved_version_id}`).then((v) => setBars(v.timeline ?? null));
  }, [song, songs]);

  async function send(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setState("sending");
    try {
      await post("/api/feedback", { song_id: song, bar_label: bar || null, comment });
      setState("sent");
      setComment("");
    } catch (err) {
      setError((err as Error).message);
      setState("");
    }
  }

  if (state === "sent")
    return (
      <div className="stack narrow">
        <h1>Thank you</h1>
        <p>Your note was sent without your name.</p>
        <a className="button big" href="#/">Back to songs</a>
      </div>
    );

  return (
    <form className="stack narrow" onSubmit={send}>
      <h1>Report a problem</h1>
      <p className="notice small">
        Your name, account and the exact time are <strong>not</strong> stored with this note; the director sees only
        the song, bar, your words and the week. In a small choir, wording or timing can still hint at who wrote it,
        so we do not promise perfect anonymity.
      </p>
      <label>
        Song
        <select value={song} onChange={(e) => setSong(Number(e.target.value))} required>
          <option value="">Choose…</option>
          {songs.map((s) => <option key={s.id} value={s.id}>{s.title}</option>)}
        </select>
      </label>
      <label>
        Bar (optional)
        <select value={bar} onChange={(e) => setBar(e.target.value)}>
          <option value="">Whole piece / not sure</option>
          {bars?.bars.map((b) => <option key={b.index} value={b.label}>{barName(b)}</option>)}
        </select>
      </label>
      <label>
        What is wrong or unclear?
        <textarea value={comment} maxLength={1000} required onChange={(e) => setComment(e.target.value)}
          placeholder="For example: the tenor note on beat 3 sounds different from my printed copy" />
      </label>
      {error && <p className="error">{error}</p>}
      <button className="big primary" disabled={state === "sending" || !song}>Send</button>
    </form>
  );
}
