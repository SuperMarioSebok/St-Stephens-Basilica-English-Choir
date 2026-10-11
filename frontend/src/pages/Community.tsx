import { useEffect, useState } from "react";
import { get, post, send, type Me, type SiteSettings } from "../lib/api";
import { formatWhen, QR } from "./Shared";

type Tab = "week" | "enquiries" | "events" | "invites" | "survey" | "page";

const STATUS_LABELS: Record<string, string> = {
  new: "New", contacted: "Contacted", first_rehearsal: "Came to a rehearsal", probation: "On probation",
  joined: "Joined", volunteer: "Volunteer", not_now: "Not now",
};

export default function Community({ me }: { me: Me }) {
  const tabs: [Tab, string, boolean][] = [
    ["week", "This week", true],
    ["enquiries", "Enquiries", me.role !== "comms"],
    ["events", "Events", true],
    ["invites", "Invites", me.role === "director"],
    ["survey", "Member survey", me.role === "director"],
    ["page", "Public page", true],
  ];
  const [tab, setTab] = useState<Tab>(() => {
    try {
      return (localStorage.getItem("bvc-community-tab") as Tab) || "week";
    } catch {
      return "week";
    }
  });
  const choose = (t: Tab) => {
    setTab(t);
    try {
      localStorage.setItem("bvc-community-tab", t);
    } catch {
      /* private mode */
    }
  };
  const visible = tabs.filter(([, , ok]) => ok);
  const current = visible.some(([t]) => t === tab) ? tab : "week";
  return (
    <div className="stack">
      <h1>Community</h1>
      <div className="seg">
        {visible.map(([t, label]) => (
          <button key={t} className={t === current ? "on" : ""} onClick={() => choose(t)}>{label}</button>
        ))}
      </div>
      {current === "week" && <Week me={me} />}
      {current === "enquiries" && <Enquiries me={me} />}
      {current === "events" && <Events me={me} />}
      {current === "invites" && <Invites />}
      {current === "survey" && <Survey />}
      {current === "page" && <PageSettings me={me} />}
    </div>
  );
}

// ---- This week -------------------------------------------------------------------------------

interface WeekRow { week: string; enquiries: number; singers: number; volunteers_supporters: number; contacted: number; first_rehearsal: number; probation: number; joined: number }
interface Kpi {
  weeks: WeekRow[];
  totals: Record<string, number>;
  sources_open_enquiries: { source: string; n: number }[];
  snapshots: { week: string; metric: string; value: number }[];
  events: { id: number; title: string; starts_at: string; reserved: number; actual_attendance: number | null; donations_reported_huf: number | null }[];
}
const METRICS: [string, string][] = [
  ["followers_instagram", "Instagram followers"], ["followers_facebook", "Facebook followers"],
  ["followers_youtube", "YouTube subscribers"], ["followers_tiktok", "TikTok followers"],
  ["active_singers", "Active singers"], ["volunteers", "Volunteers"], ["rehearsal_attendance", "Rehearsal attendance (headcount)"],
];

function Week({ me }: { me: Me }) {
  const [kpi, setKpi] = useState<Kpi | null>(null);
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");
  const load = () => get<Kpi>("/api/kpi").then(setKpi).catch((e) => setError(e.message));
  useEffect(() => void load(), []);
  if (error) return <p className="error">{error}</p>;
  if (!kpi) return <p>Loading…</p>;
  const w = kpi.weeks[kpi.weeks.length - 1];
  const canSnapshot = me.role === "director" || me.role === "comms";
  return (
    <div className="stack">
      <section className="card">
        <h2>Week {w.week}</h2>
        <div className="tiles">
          {([["New enquiries", w.enquiries], ["Want to sing", w.singers], ["Volunteer or support", w.volunteers_supporters],
            ["Contacted", w.contacted], ["First rehearsals", w.first_rehearsal], ["On probation", w.probation], ["Joined", w.joined]] as [string, number][]).map(([l, n]) => (
            <div key={l} className="tile"><strong>{n}</strong><span>{l}</span></div>
          ))}
        </div>
        <p className="small muted">Counts only, no names. <a href="/api/kpi.csv">Download the last 12 weeks (CSV)</a></p>
      </section>
      <section className="card">
        <h2>Since the start</h2>
        <p>
          {kpi.totals.new ?? 0} enquiries · {kpi.totals.first_rehearsal ?? 0} came to a rehearsal ·{" "}
          {kpi.totals.probation ?? 0} on probation · {kpi.totals.joined ?? 0} joined
        </p>
        {kpi.sources_open_enquiries.length > 0 && (
          <p className="small muted">Where open enquiries came from: {kpi.sources_open_enquiries.map((s) => `${s.source} ${s.n}`).join(" · ")}</p>
        )}
      </section>
      {kpi.events.length > 0 && (
        <section className="card">
          <h2>Events</h2>
          <table className="mixer"><tbody>
            {kpi.events.map((e) => (
              <tr key={e.id}><th>{e.title}</th><td>{e.reserved} reserved</td><td>{e.actual_attendance ?? "–"} attended</td>
                <td>{e.donations_reported_huf != null ? `${e.donations_reported_huf.toLocaleString("en-GB")} HUF reported` : "–"}</td></tr>
            ))}
          </tbody></table>
        </section>
      )}
      {canSnapshot && (
        <form className="card stack tight" onSubmit={(e) => {
          e.preventDefault();
          const f = new FormData(e.currentTarget);
          post("/api/kpi/snapshots", { metric: f.get("metric"), value: Number(f.get("value")) })
            .then(() => { setMsg("Saved."); void load(); }).catch((err) => setMsg(err.message));
        }}>
          <h2>Friday numbers</h2>
          <p className="small muted">Type this week's numbers from each platform. Saving again replaces the value for this week.</p>
          <div className="row wrap">
            <select id="snap_metric" name="metric">{METRICS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select>
            <input id="snap_value" name="value" type="number" min={0} required style={{ maxWidth: 140 }} />
            <button className="primary">Save</button>
          </div>
          {msg && <p className="small">{msg}</p>}
          {kpi.snapshots.length > 0 && (
            <table className="mixer"><tbody>
              {kpi.snapshots.slice(0, 14).map((s) => (
                <tr key={`${s.week}-${s.metric}`}><td>{s.week}</td><th>{METRICS.find(([k]) => k === s.metric)?.[1] ?? s.metric}</th><td>{s.value}</td></tr>
              ))}
            </tbody></table>
          )}
        </form>
      )}
    </div>
  );
}

// ---- Enquiries ---------------------------------------------------------------------------------

interface Enquiry {
  id: string; created_on: string; first_name: string; contact: string; interests: string[]; voice_type: string | null;
  message: string; under_18: number; guardian_name: string | null; guardian_contact: string | null;
  updates_opt_in: number; source: string | null; status: string; notes: string;
}

function Enquiries({ me }: { me: Me }) {
  const [rows, setRows] = useState<Enquiry[] | null>(null);
  const [error, setError] = useState("");
  const [invite, setInvite] = useState<{ name: string; link: string } | null>(null);
  const load = () => get<Enquiry[]>("/api/enquiries").then(setRows).catch((e) => setError(e.message));
  useEffect(() => void load(), []);
  if (error) return <p className="error">{error}</p>;
  if (!rows) return <p>Loading…</p>;
  const act = (p: Promise<unknown>) => p.then(load).catch((e) => setError(e.message));
  return (
    <div className="stack">
      <p className="small muted">Only the welcome team and directors see this list. Entries are deleted 6 months after their last change, and when the person joins with an invite.</p>
      {invite && <InviteResult name={invite.name} link={invite.link} onClose={() => setInvite(null)} />}
      {rows.length === 0 && <p className="muted">No enquiries yet.</p>}
      <ul className="cards">
        {rows.map((r) => (
          <li key={r.id} className="card stack tight">
            <div className="row wrap" style={{ justifyContent: "space-between" }}>
              <h3 style={{ margin: 0 }}>{r.first_name}{r.under_18 ? " (under 18)" : ""}</h3>
              <span className="tag">{STATUS_LABELS[r.status] ?? r.status}</span>
            </div>
            <p className="small">
              {r.contact} · {r.interests.join(", ")}{r.voice_type ? ` · ${r.voice_type}` : ""} · {r.created_on}
              {r.source ? ` · via ${r.source}` : ""}{r.updates_opt_in ? " · wants concert news" : ""}
            </p>
            {r.under_18 ? <p className="small warn">Contact the parent or guardian: {r.guardian_name}, {r.guardian_contact}</p> : null}
            {r.message && <p className="prewrap">{r.message}</p>}
            <div className="row wrap">
              <select aria-label="Status" value={r.status} onChange={(e) => act(send("PATCH", `/api/enquiries/${r.id}`, { status: e.target.value }))}>
                {Object.entries(STATUS_LABELS).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
              </select>
              {me.role === "director" && r.status === "probation" && (
                <button onClick={() => {
                  const part = r.voice_type ? ({ soprano: "S", alto: "A", tenor: "T", bass: "B" } as Record<string, string>)[r.voice_type] : null;
                  post<{ token: string }>("/api/invites", { display_name: r.first_name, role: "singer", voice_part: part ?? null, enquiry_id: r.id })
                    .then((x) => setInvite({ name: r.first_name, link: inviteLink(x.token) })).catch((e) => setError(e.message));
                }}>Create app invite</button>
              )}
              <button onClick={() => act(send("DELETE", `/api/enquiries/${r.id}`))}>Delete</button>
            </div>
            <label className="small">Notes
              <textarea defaultValue={r.notes} maxLength={2000} onBlur={(e) => {
                if (e.target.value !== r.notes) void act(send("PATCH", `/api/enquiries/${r.id}`, { notes: e.target.value }));
              }} />
            </label>
          </li>
        ))}
      </ul>
    </div>
  );
}

const inviteLink = (token: string) => `${window.location.origin}/#/invite/${token}`;

function InviteResult({ name, link, onClose }: { name: string; link: string; onClose: () => void }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="card stack tight notice">
      <h3>Invite for {name}</h3>
      <p className="small">Send this link privately (for example in WhatsApp), or let them scan the code. It works once and expires in 14 days.</p>
      <QR value={link} />
      <code className="break">{link}</code>
      <div className="row">
        <button onClick={() => navigator.clipboard.writeText(link).then(() => setCopied(true)).catch(() => undefined)}>{copied ? "Copied ✓" : "Copy link"}</button>
        <button onClick={onClose}>Done</button>
      </div>
    </div>
  );
}

// ---- Events --------------------------------------------------------------------------------------

interface EventRow {
  id: number; title: string; starts_at: string; venue: string; description: string; is_public: number; rsvp_open: number;
  capacity: number | null; actual_attendance: number | null; donations_reported_huf: number | null; reserved: number;
}

interface Guest { first_name: string; contact: string; party_size: number; cancelled: number }

function Events({ me }: { me: Me }) {
  const [rows, setRows] = useState<EventRow[] | null>(null);
  const [editing, setEditing] = useState<EventRow | "new" | null>(null);
  const [error, setError] = useState("");
  const [guests, setGuests] = useState<{ id: number; list: Guest[] } | null>(null);
  const load = () => get<EventRow[]>("/api/events").then(setRows).catch((e) => setError(e.message));
  useEffect(() => void load(), []);
  if (error) return <p className="error">{error}</p>;
  if (!rows) return <p>Loading…</p>;
  const director = me.role === "director";
  return (
    <div className="stack">
      {director && !editing && <button className="primary" onClick={() => setEditing("new")}>Add an event</button>}
      {editing && <EventForm event={editing === "new" ? null : editing} onDone={() => { setEditing(null); void load(); }} />}
      {rows.length === 0 && <p className="muted">No events yet. Add the Christmas Concert to start the countdown.</p>}
      {rows.map((e) => (
        <div key={e.id} className="card stack tight">
          <h3 style={{ margin: 0 }}>{e.title}</h3>
          <p className="small">{formatWhen(e.starts_at)}{e.venue && ` · ${e.venue}`} · {e.is_public ? "public" : "not public"} · {e.rsvp_open ? "reservations open" : "reservations closed"}</p>
          <p className="small">{e.reserved} reserved{e.capacity != null ? ` of ${e.capacity}` : ""} · {e.actual_attendance ?? "–"} attended · {e.donations_reported_huf != null ? `${e.donations_reported_huf.toLocaleString("en-GB")} HUF reported` : "donations not entered"}</p>
          <div className="row wrap">
            {director && <button onClick={() => setEditing(e)}>Edit</button>}
            {me.role !== "comms" && <button onClick={() => get<Guest[]>(`/api/events/${e.id}/reservations`).then((list) => setGuests({ id: e.id, list })).catch((err) => setError(err.message))}>Reservations</button>}
            <a className="button" href={`#/event/${e.id}`}>Public page</a>
          </div>
          {guests?.id === e.id && (
            <table className="mixer"><tbody>
              {guests.list.length === 0 && <tr><td>No reservations yet.</td></tr>}
              {guests.list.map((g, i) => <tr key={i} className={g.cancelled ? "muted" : ""}><th>{g.first_name}</th><td>{g.party_size}</td><td>{g.contact}</td><td>{g.cancelled ? "cancelled" : ""}</td></tr>)}
            </tbody></table>
          )}
          <div className="row wrap"><QR value={`${window.location.origin}/?src=qr#/event/${e.id}`} size={140} /><p className="small muted">QR code for posters and cards: opens this event's page.</p></div>
        </div>
      ))}
    </div>
  );
}

function EventForm({ event, onDone }: { event: EventRow | null; onDone: () => void }) {
  const [error, setError] = useState("");
  const local = event ? event.starts_at.slice(0, 16) : "";
  return (
    <form className="card stack tight" onSubmit={(e) => {
      e.preventDefault();
      const f = new FormData(e.currentTarget);
      const num = (k: string) => (f.get(k) === "" ? null : Number(f.get(k)));
      const body = {
        title: f.get("title"), starts_at: f.get("starts_at"), venue: f.get("venue"), description: f.get("description"),
        is_public: f.get("is_public") === "on", rsvp_open: f.get("rsvp_open") === "on", capacity: num("capacity"),
        actual_attendance: num("actual_attendance"), donations_reported_huf: num("donations_reported_huf"),
      };
      (event ? send("PUT", `/api/events/${event.id}`, body) : post("/api/events", body)).then(onDone).catch((err) => setError(err.message));
    }}>
      <h2>{event ? "Edit event" : "New event"}</h2>
      <label>Title<input id="ev_title" name="title" required defaultValue={event?.title ?? "Christmas Concert"} maxLength={120} /></label>
      <label>Date and time (Budapest time)<input id="ev_start" name="starts_at" type="datetime-local" required defaultValue={local} /></label>
      <label>Venue<input id="ev_venue" name="venue" defaultValue={event?.venue ?? ""} maxLength={200} /></label>
      <label>Description<textarea id="ev_desc" name="description" defaultValue={event?.description ?? ""} maxLength={2000} /></label>
      <label className="inline"><input type="checkbox" name="is_public" defaultChecked={!!event?.is_public} /> Show on the public page (countdown)</label>
      <label className="inline"><input type="checkbox" name="rsvp_open" defaultChecked={!!event?.rsvp_open} /> Allow free reservations</label>
      <label>Places available for reservation (empty = no limit)<input id="ev_cap" name="capacity" type="number" min={0} defaultValue={event?.capacity ?? ""} /></label>
      <fieldset className="stack tight"><legend>After the event</legend>
        <label>Headcount (people who came)<input id="ev_att" name="actual_attendance" type="number" min={0} defaultValue={event?.actual_attendance ?? ""} /></label>
        <label>Donations reported by the parish or charity (HUF)<input id="ev_don" name="donations_reported_huf" type="number" min={0} defaultValue={event?.donations_reported_huf ?? ""} /></label>
        <p className="small muted">The choir handles no money. Enter only the total the parish or charity reports.</p>
      </fieldset>
      {error && <p className="error">{error}</p>}
      <div className="row"><button className="primary">Save</button><button type="button" onClick={onDone}>Cancel</button></div>
    </form>
  );
}

// ---- Invites ------------------------------------------------------------------------------------

interface InviteRow { id: number; display_name: string; role: string; voice_part: string | null; created_at: string; expires_at: string; state: string }

function Invites() {
  const [rows, setRows] = useState<InviteRow[] | null>(null);
  const [result, setResult] = useState<{ name: string; link: string } | null>(null);
  const [error, setError] = useState("");
  const load = () => get<InviteRow[]>("/api/invites").then(setRows).catch((e) => setError(e.message));
  useEffect(() => void load(), []);
  return (
    <div className="stack">
      <form className="card stack tight" onSubmit={(e) => {
        e.preventDefault();
        const f = new FormData(e.currentTarget);
        const name = String(f.get("display_name"));
        post<{ token: string }>("/api/invites", { display_name: name, role: f.get("role"), voice_part: f.get("voice_part") || null })
          .then((x) => { setResult({ name, link: inviteLink(x.token) }); void load(); }).catch((err) => setError(err.message));
      }}>
        <h2>Invite someone to the app</h2>
        <label>Name<input id="inv_name" name="display_name" required maxLength={60} /></label>
        <div className="row wrap">
          <label>Role
            <select id="inv_role" name="role" defaultValue="singer">
              <option value="singer">Singer</option><option value="voice_lead">Voice lead</option><option value="director">Director</option>
              <option value="welcome">Welcome team</option><option value="comms">Communications team</option>
            </select>
          </label>
          <label>Voice part
            <select id="inv_part" name="voice_part" defaultValue="">
              <option value="">None</option><option value="S">Soprano</option><option value="A">Alto</option><option value="T">Tenor</option><option value="B">Bass</option>
            </select>
          </label>
        </div>
        <button className="primary">Create invite</button>
        {error && <p className="error">{error}</p>}
      </form>
      {result && <InviteResult name={result.name} link={result.link} onClose={() => setResult(null)} />}
      {rows && rows.length > 0 && (
        <table className="mixer"><tbody>
          {rows.map((r) => (
            <tr key={r.id}><th>{r.display_name}</th><td>{r.role}{r.voice_part ? ` ${r.voice_part}` : ""}</td><td>{r.state}</td>
              <td>{(r.state === "pending" || r.state === "expired") && (
                <button onClick={() => post<{ token: string }>(`/api/invites/${r.id}/resend`).then((x) => { setResult({ name: r.display_name, link: inviteLink(x.token) }); void load(); }).catch((e) => setError(e.message))}>New link</button>
              )}</td></tr>
          ))}
        </tbody></table>
      )}
    </div>
  );
}

// ---- Member survey -----------------------------------------------------------------------------

interface SurveyResult { id: number; title: string; question: string; is_open: boolean; responses: number; nps?: number; promoters?: number; passives?: number; detractors?: number; comments?: string[]; note?: string }

function Survey() {
  const [rows, setRows] = useState<SurveyResult[] | null>(null);
  const [error, setError] = useState("");
  const load = () => get<SurveyResult[]>("/api/surveys/results").then(setRows).catch((e) => setError(e.message));
  useEffect(() => void load(), []);
  return (
    <div className="stack">
      <form className="card stack tight" onSubmit={(e) => {
        e.preventDefault();
        const f = new FormData(e.currentTarget);
        post("/api/surveys", { title: f.get("title") }).then(load).catch((err) => setError(err.message));
        e.currentTarget.reset();
      }}>
        <h2>Ask members one question</h2>
        <p className="small muted">"How likely are you to recommend singing with our choir to a friend? (0–10)" plus an optional comment. Members see it on their songs page. Answers carry no names; results appear once 5 people have answered.</p>
        <div className="row wrap"><input id="sv_title" name="title" required maxLength={80} placeholder="e.g. Baseline, November 2026" /><button className="primary">Open survey</button></div>
        {error && <p className="error">{error}</p>}
      </form>
      {rows?.map((s) => (
        <div key={s.id} className="card stack tight">
          <h3 style={{ margin: 0 }}>{s.title} {s.is_open ? <span className="tag">open</span> : <span className="tag">closed</span>}</h3>
          <p className="small">{s.responses} answers</p>
          {s.nps !== undefined ? (
            <>
              <p className="nps">Score <strong>{s.nps > 0 ? `+${s.nps}` : s.nps}</strong> <span className="small muted">({s.promoters} would recommend · {s.passives} neutral · {s.detractors} unlikely)</span></p>
              {s.comments && s.comments.length > 0 && <ul>{s.comments.map((c, i) => <li key={i}>{c}</li>)}</ul>}
            </>
          ) : <p className="small muted">{s.note}</p>}
          {s.is_open && <button onClick={() => post(`/api/surveys/${s.id}/close`).then(load).catch((e) => setError(e.message))}>Close survey</button>}
        </div>
      ))}
    </div>
  );
}

// ---- Public page settings --------------------------------------------------------------------

const FIELDS: [keyof SiteSettings, string, boolean][] = [
  ["headline", "Headline", false], ["choir_name", "Choir name (always 'the English Choir of St. Stephen's Basilica')", false],
  ["mission", "Mission line", false], ["about", "Who we are", true], ["rehearsals", "When and where we rehearse", true],
  ["what_to_expect", "What to expect", true], ["join_deadline_text", "Deadline sentence", false],
  ["join_deadline", "Sign-up deadline (YYYY-MM-DD)", false], ["support_text", "Other ways to help", true],
  ["donation_url", "Donation link (parish or charity page only, https://…)", false], ["donation_text", "Donation button text", false],
  ["privacy_text", "Privacy sentence next to the consent box", true],
];

function PageSettings({ me }: { me: Me }) {
  const [s, setS] = useState<SiteSettings | null>(null);
  const [msg, setMsg] = useState("");
  useEffect(() => { get<SiteSettings>("/api/site").then(setS).catch((e) => setMsg(e.message)); }, []);
  if (!s) return <p>{msg || "Loading…"}</p>;
  const director = me.role === "director";
  const joinLink = `${window.location.origin}/?src=qr#/join`;
  return (
    <form className="stack" onSubmit={(e) => {
      e.preventDefault();
      const f = new FormData(e.currentTarget);
      const values: Record<string, string> = {};
      FIELDS.forEach(([k]) => { values[k] = String(f.get(k) ?? ""); });
      send<SiteSettings>("PUT", "/api/site", values).then((x) => { setS(x); setMsg("Saved."); }).catch((err) => setMsg(err.message));
    }}>
      <div className="card stack tight">
        <h2>Status: {s.published === "1" ? "published" : "not published (preview only)"}</h2>
        <p className="small muted">Publish only after the parish priest and the choir master have approved the wording.</p>
        <div className="row wrap">
          <a className="button" href="#/join">Preview the page</a>
          {director && (
            <button type="button" className={s.published === "1" ? "" : "primary"} onClick={() =>
              send<SiteSettings>("PUT", "/api/site", { published: s.published === "1" ? "0" : "1" }).then((x) => { setS(x); setMsg(x.published === "1" ? "Published." : "Unpublished."); }).catch((err) => setMsg(err.message))
            }>{s.published === "1" ? "Unpublish" : "Publish"}</button>
          )}
        </div>
        <div className="row wrap"><QR value={joinLink} size={160} /><p className="small muted">QR code for the "Come sing with us" page, for posters and the church door.</p></div>
      </div>
      {FIELDS.map(([k, label, long]) => (
        <label key={k}>{label}
          {long
            ? <textarea id={`set_${k}`} name={k} defaultValue={s[k]} disabled={!director} maxLength={2000} />
            : <input id={`set_${k}`} name={k} defaultValue={s[k]} disabled={!director} maxLength={300} />}
        </label>
      ))}
      {director && <button className="big primary">Save wording</button>}
      {msg && <p role="status">{msg}</p>}
    </form>
  );
}
