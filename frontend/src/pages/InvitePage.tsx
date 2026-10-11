import { useEffect, useState } from "react";
import { get, PART_NAMES, post, type Part } from "../lib/api";

const ROLE_NAMES: Record<string, string> = {
  singer: "singer", voice_lead: "voice lead", director: "director", welcome: "welcome team", comms: "communications team",
};

export default function InvitePage({ token, onJoined }: { token: string; onJoined: () => void }) {
  const [info, setInfo] = useState<{ display_name: string; role: string; voice_part: Part | null } | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    get<typeof info>(`/api/public/invites/${encodeURIComponent(token)}`).then(setInfo).catch((e) => setError(e.message));
  }, [token]);

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    if (f.get("password") !== f.get("password2")) return setError("The two passwords are different");
    setBusy(true);
    setError("");
    try {
      await post(`/api/public/invites/${encodeURIComponent(token)}/accept`, {
        username: f.get("username"), password: f.get("password"),
      });
      window.location.hash = "/";
      onJoined();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (!info) return <main className="page narrow"><h1>Welcome</h1><p className={error ? "error" : ""}>{error || "Checking your invite…"}</p></main>;
  return (
    <main className="page narrow">
      <h1>Welcome, {info.display_name}!</h1>
      <p>
        You're invited to Basilica Voice Coach as a {ROLE_NAMES[info.role] ?? info.role}
        {info.voice_part ? ` (${PART_NAMES[info.voice_part]})` : ""}. Choose a username and password to finish.
      </p>
      <form className="stack" onSubmit={submit}>
        <label>Username (lowercase, e.g. anna.k)
          <input id="i_username" name="username" required minLength={3} maxLength={32} autoCapitalize="none" autoComplete="username" />
        </label>
        <label>Password (at least 10 characters)
          <input id="i_password" name="password" type="password" required minLength={10} autoComplete="new-password" />
        </label>
        <label>Password again
          <input id="i_password2" name="password2" type="password" required minLength={10} autoComplete="new-password" />
        </label>
        {error && <p className="error">{error}</p>}
        <button className="big primary" disabled={busy}>Start practising</button>
      </form>
      <p className="muted small">Tip: after logging in, use your browser's "Add to Home screen" to keep the app one tap away.</p>
    </main>
  );
}
