import { useState } from "react";
import { go } from "../App";
import { postForm } from "../lib/api";

export default function Upload() {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent<HTMLFormElement>, path: string) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const r = await postForm<{ version_id: number }>(path, new FormData(e.currentTarget));
      go(`/review/${r.version_id}`);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="stack">
      <h1>Add a song</h1>
      <p className="notice small">
        Upload only material the choir has permission to use for member practice. Record the source and permission
        in the rights note; it stays with the song.
      </p>
      {error && <p className="error">{error}</p>}

      <form className="card stack tight" onSubmit={(e) => submit(e, "/api/songs")}>
        <h2>From a MusicXML score (preferred)</h2>
        <label>Score file (.musicxml, .xml or .mxl, up to 5 MB)
          <input type="file" name="score" accept=".musicxml,.xml,.mxl" required />
        </label>
        <label>Title (optional, otherwise taken from the file)
          <input name="title" maxLength={120} />
        </label>
        <label>Rights note: composer, arranger, edition, who gave permission
          <textarea name="rights_note" required maxLength={1000} />
        </label>
        <label className="inline"><input type="checkbox" name="is_test_piece" value="true" /> This is a test piece, not choir repertoire</label>
        <button className="primary" disabled={busy}>Upload and check parts</button>
      </form>

      <form className="card stack tight" onSubmit={(e) => submit(e, "/api/songs/manual")}>
        <h2>Fallback: recording plus PDF</h2>
        <p className="small muted">For pieces without a usable MusicXML. Singers get time-based repeats only.</p>
        <label>Title<input name="title" required maxLength={120} /></label>
        <label>Practice recording (.mp3, .m4a, .ogg, .wav, up to 40 MB)
          <input type="file" name="audio" accept=".mp3,.m4a,.ogg,.wav" required />
        </label>
        <label>Score PDF (optional, up to 20 MB)<input type="file" name="pdf" accept=".pdf,application/pdf" /></label>
        <label>Note for singers (optional)<input name="note" maxLength={500} placeholder="e.g. the recording starts at bar 1, no count-in" /></label>
        <label>Rights note: who made the recording and who permitted its use
          <textarea name="rights_note" required maxLength={1000} />
        </label>
        <button className="primary" disabled={busy}>Upload recording</button>
      </form>
    </div>
  );
}
