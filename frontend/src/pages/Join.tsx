import { useEffect, useState } from "react";
import { get, post, sourceParam, type PublicEvent, type PublicPage } from "../lib/api";
import { Countdown, formatDate, formatWhen, ShareButtons } from "./Shared";

const INTERESTS: [string, string][] = [
  ["sing", "Sing in the choir"],
  ["volunteer", "Volunteer (concerts, video, design, welcome)"],
  ["support", "Support the choir in other ways"],
  ["concert", "Come to the Christmas Concert"],
];

export default function Join() {
  const [page, setPage] = useState<PublicPage | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    get<PublicPage>("/api/public/page").then(setPage).catch((e) => setError(e.message));
  }, []);
  if (error) return <main className="page narrow"><h1>Coming soon</h1><p className="muted">{error}</p></main>;
  if (!page) return <main className="page"><p>Loading…</p></main>;
  const s = page.settings;
  const next = page.events[0];
  const deadline = s.join_deadline ? `${s.join_deadline}T23:59:00+02:00` : "";

  return (
    <main className="page public">
      {page.preview && <p className="notice">Preview: this page is not public yet. A director publishes it once the wording is approved.</p>}
      <header className="hero">
        <p className="eyebrow">{s.choir_name}</p>
        <h1>{s.headline}</h1>
        <p className="mission">{s.mission}</p>
      </header>

      <div className="countdowns">
        {deadline && (
          <Countdown target={deadline} label={`${s.join_deadline_text} ${formatDate(s.join_deadline)}`} />
        )}
        {next && <Countdown target={next.starts_at} label={`${next.title}, ${formatWhen(next.starts_at)}`} />}
      </div>

      <section className="card">
        <h2>Who we are</h2>
        <p>{s.about}</p>
        <h2>When and where we rehearse</h2>
        <p className="prewrap">{s.rehearsals}</p>
        <h2>What to expect</h2>
        <p>{s.what_to_expect}</p>
      </section>

      <InterestForm privacy={s.privacy_text} />

      {page.events.length > 0 && (
        <section className="stack">
          <h2>Coming up</h2>
          {page.events.map((e) => <EventCard key={e.id} event={e} />)}
        </section>
      )}

      <section className="card">
        <h2>Other ways to help</h2>
        <p>{s.support_text}</p>
        {s.donation_url && (
          <p>
            <a className="button" href={s.donation_url} target="_blank" rel="noopener">
              {s.donation_text || "Give through the parish"}
            </a>
          </p>
        )}
        <h2>Invite a friend</h2>
        <ShareButtons text={`${s.headline}: ${s.choir_name}.`} hash="/join" />
      </section>
      <p className="muted small"><a href="#/login">Choir members: log in</a></p>
    </main>
  );
}

function EventCard({ event }: { event: PublicEvent }) {
  return (
    <div className="card">
      <h3>{event.title}</h3>
      <p><strong>{formatWhen(event.starts_at)}</strong>{event.venue && ` · ${event.venue}`}</p>
      {event.description && <p className="prewrap">{event.description}</p>}
      <div className="row wrap">
        {event.rsvp_open && (event.places_left === null || event.places_left > 0) && (
          <a className="button primary" href={`#/event/${event.id}`}>Reserve a place</a>
        )}
        {event.places_left === 0 && <span className="tag">Fully reserved</span>}
      </div>
      <ShareButtons text={`${event.title}, ${formatWhen(event.starts_at)}`} hash={`/event/${event.id}`} />
    </div>
  );
}

function InterestForm({ privacy }: { privacy: string }) {
  const [interests, setInterests] = useState<string[]>(["sing"]);
  const [under18, setUnder18] = useState(false);
  const [state, setState] = useState<"" | "sending" | "sent">("");
  const [error, setError] = useState("");

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setError("");
    setState("sending");
    try {
      await post("/api/public/enquiries", {
        first_name: f.get("first_name"), contact: f.get("contact"), interests,
        voice_type: f.get("voice_type") || null, message: f.get("message") || "",
        consent: f.get("consent") === "on", updates_opt_in: f.get("updates") === "on",
        under_18: under18, guardian_name: f.get("guardian_name") || null,
        guardian_contact: f.get("guardian_contact") || null, guardian_consent: f.get("guardian_consent") === "on",
        source: sourceParam(), website: f.get("website") || "",
      });
      setState("sent");
    } catch (err) {
      setError((err as Error).message);
      setState("");
    }
  }

  if (state === "sent")
    return (
      <section className="card">
        <h2>Thank you!</h2>
        <p>Someone from the choir will get in touch with you personally. We look forward to meeting you.</p>
      </section>
    );

  const toggle = (k: string) => setInterests((x) => (x.includes(k) ? x.filter((i) => i !== k) : [...x, k]));
  return (
    <form className="card stack tight" onSubmit={submit} id="interest">
      <h2>I'd like to join or help</h2>
      <fieldset className="stack tight">
        <legend>I'd like to (tick any)</legend>
        {INTERESTS.map(([k, label]) => (
          <label key={k} className="inline">
            <input type="checkbox" checked={interests.includes(k)} onChange={() => toggle(k)} /> {label}
          </label>
        ))}
      </fieldset>
      <label>First name<input id="first_name" name="first_name" required maxLength={60} autoComplete="given-name" /></label>
      <label>Email or phone<input id="contact" name="contact" required maxLength={120} autoComplete="email" /></label>
      {interests.includes("sing") && (
        <label>Voice type
          <select id="voice_type" name="voice_type" defaultValue="not sure">
            <option value="not sure">Not sure</option>
            <option value="soprano">Soprano</option>
            <option value="alto">Alto</option>
            <option value="tenor">Tenor</option>
            <option value="bass">Bass</option>
          </select>
        </label>
      )}
      <label>Anything you'd like us to know? (optional)<textarea id="message" name="message" maxLength={1000} /></label>
      <label className="inline"><input type="checkbox" checked={under18} onChange={(e) => setUnder18(e.target.checked)} /> I am under 18</label>
      {under18 && (
        <div className="stack tight guardian">
          <label>Parent or guardian's name<input id="guardian_name" name="guardian_name" required maxLength={80} /></label>
          <label>Parent or guardian's email or phone<input id="guardian_contact" name="guardian_contact" required maxLength={120} /></label>
          <label className="inline"><input type="checkbox" name="guardian_consent" required /> I am the parent or guardian and I agree that the choir may contact us about this.</label>
        </div>
      )}
      <input className="hp" name="website" tabIndex={-1} autoComplete="off" aria-hidden="true" />
      <label className="inline"><input type="checkbox" name="consent" required /> I agree that the choir may keep these details to reply to me. {privacy}</label>
      <label className="inline"><input type="checkbox" name="updates" /> Keep me updated about concerts (optional).</label>
      {error && <p className="error">{error}</p>}
      <button className="big primary" disabled={state === "sending" || interests.length === 0}>Send</button>
    </form>
  );
}
