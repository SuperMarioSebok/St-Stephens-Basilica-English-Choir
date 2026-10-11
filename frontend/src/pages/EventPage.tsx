import { useEffect, useState } from "react";
import { get, post, sourceParam, type PublicPage } from "../lib/api";
import { Countdown, formatWhen, ShareButtons } from "./Shared";

export default function EventPage({ eventId }: { eventId: number }) {
  const [page, setPage] = useState<PublicPage | null>(null);
  const [error, setError] = useState("");
  const [code, setCode] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    get<PublicPage>("/api/public/page").then(setPage).catch((e) => setError(e.message));
  }, []);
  if (error && !page) return <main className="page narrow"><p className="error">{error}</p></main>;
  if (!page) return <main className="page"><p>Loading…</p></main>;
  const event = page.events.find((e) => e.id === eventId);
  if (!event) return <main className="page narrow"><p>This event is not available.</p><a href="#/join">Back</a></main>;

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setBusy(true);
    setError("");
    try {
      const r = await post<{ cancel_code: string | null }>("/api/public/reservations", {
        event_id: eventId, first_name: f.get("first_name"), contact: f.get("contact"),
        party_size: Number(f.get("party_size") || 1), consent: f.get("consent") === "on",
        updates_opt_in: f.get("updates") === "on", source: sourceParam(), website: f.get("website") || "",
      });
      setCode(r.cancel_code ?? "");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="page public narrow">
      <p className="eyebrow">{page.settings.choir_name}</p>
      <h1>{event.title}</h1>
      <p><strong>{formatWhen(event.starts_at)}</strong>{event.venue && ` · ${event.venue}`}</p>
      <Countdown target={event.starts_at} label="Starts in" />
      {event.description && <p className="prewrap">{event.description}</p>}

      {code !== null ? (
        <section className="card">
          <h2>Your place is reserved</h2>
          <p>Thank you! We look forward to seeing you.</p>
          {code && (
            <p className="small">
              If you can't come, cancel here so someone else can have your place:{" "}
              <a href={`#/cancel/${code}`}>cancel my reservation</a>. Keep this page or note the code: <code>{code}</code>
            </p>
          )}
          <h2>Bring friends</h2>
          <ShareButtons text={`${event.title}, ${formatWhen(event.starts_at)}`} hash={`/event/${event.id}`} />
        </section>
      ) : event.rsvp_open ? (
        <form className="card stack tight" onSubmit={submit}>
          <h2>Reserve a place</h2>
          {event.places_left !== null && <p className="muted">{event.places_left} places left</p>}
          <p className="small muted">Reserving is free. It helps us plan seating and welcome you.</p>
          <label>First name<input id="r_first_name" name="first_name" required maxLength={60} autoComplete="given-name" /></label>
          <label>Email or phone<input id="r_contact" name="contact" required maxLength={120} autoComplete="email" /></label>
          <label>Number of people
            <select id="r_party" name="party_size" defaultValue="1">
              {Array.from({ length: 10 }, (_, i) => i + 1).map((n) => <option key={n} value={n}>{n}</option>)}
            </select>
          </label>
          <input className="hp" name="website" tabIndex={-1} autoComplete="off" aria-hidden="true" />
          <label className="inline"><input type="checkbox" name="consent" required /> I agree that the choir may keep these details until 30 days after the event, only to manage reservations.</label>
          <label className="inline"><input type="checkbox" name="updates" /> Tell me about future concerts (optional).</label>
          {error && <p className="error">{error}</p>}
          <button className="big primary" disabled={busy}>Reserve</button>
        </form>
      ) : (
        <p className="notice">Reservations are not open for this event. Everyone is welcome.</p>
      )}
      <ShareButtons text={`${event.title}, ${formatWhen(event.starts_at)}`} hash={`/event/${event.id}`} />
      <p><a href="#/join">About the choir and how to join</a></p>
    </main>
  );
}

export function CancelPage({ code }: { code: string }) {
  const [state, setState] = useState<"" | "done" | "error">("");
  const [msg, setMsg] = useState("");
  return (
    <main className="page narrow stack">
      <h1>Cancel a reservation</h1>
      {state === "done" ? (
        <p>Your reservation is cancelled. Thank you for letting us know.</p>
      ) : (
        <>
          <p>Press the button to cancel. This can't be undone, but you can reserve again if places are left.</p>
          <button className="big" onClick={() =>
            post("/api/public/reservations/cancel", { code }).then(() => setState("done")).catch((e) => { setState("error"); setMsg(e.message); })
          }>Cancel my reservation</button>
          {state === "error" && <p className="error">{msg}</p>}
        </>
      )}
    </main>
  );
}
