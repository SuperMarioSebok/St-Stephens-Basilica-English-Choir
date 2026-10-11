import { useEffect, useState } from "react";
import { get, isCommunityRole, type Me, type SongItem } from "../lib/api";
import SurveyCard from "./SurveyCard";

const STATUS_TEXT: Record<string, string> = {
  draft: "Draft",
  in_review: "Waiting for director review",
  approved: "Approved",
  rejected: "Changes requested",
  revoked: "Approval cancelled",
  superseded: "Superseded",
};

export default function Songs({ me }: { me: Me }) {
  const [songs, setSongs] = useState<SongItem[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    get<SongItem[]>("/api/songs").then(setSongs).catch((e) => setError(e.message));
  }, []);

  if (error) return <p className="error">{error}</p>;
  if (!songs) return <p>Loading songs…</p>;
  const staff = me.role === "director" || me.role === "voice_lead";

  return (
    <div className="stack">
      <h1>Songs</h1>
      {(me.role === "director" || isCommunityRole(me.role)) && (
        <div className="row wrap">
          {me.role === "director" && <a className="button" href="#/upload">Add a song</a>}
          {me.role === "director" && <a className="button" href="#/inbox">Read feedback</a>}
          {isCommunityRole(me.role) && <a className="button primary" href="#/community">Community: enquiries, events, survey</a>}
        </div>
      )}
      <SurveyCard />
      {songs.length === 0 && (
        <p className="muted">
          {staff ? "No songs yet." : "No approved songs yet. Your director will publish songs here."}
        </p>
      )}
      <ul className="cards">
        {songs.map((s) => (
          <li key={s.id} className="card">
            <h2>{s.title}</h2>
            {s.is_test_piece && <p className="tag">Original test piece, not a choir arrangement</p>}
            {s.kind === "manual" && <p className="tag">Recording and PDF</p>}
            {staff && (
              <p className="muted small">
                Latest: version {s.latest_number}, {STATUS_TEXT[s.latest_status ?? ""] ?? s.latest_status}
                {s.render && s.render.status !== "done" && s.render.status !== "none" && ` · audio ${s.render.status}`}
              </p>
            )}
            <div className="row wrap">
              {s.approved_version_id ? (
                <a className="button big primary" href={`#/play/${s.approved_version_id}`}>Practise</a>
              ) : (
                !staff && null
              )}
              {s.approved_version_id && (
                <a className="button" href={`#/feedback/${s.id}`}>Report a problem</a>
              )}
              {staff && s.kind === "score" && me.role === "voice_lead" && (
                <a className="button" href={`#/edit/${s.latest_version_id}`}>Edit my part</a>
              )}
              {staff && (
                <a className="button" href={`#/review/${s.latest_version_id}`}>
                  {me.role === "director" ? "Review" : "Latest version"}
                </a>
              )}
              {staff && <a className="button" href={`#/history/${s.id}`}>History</a>}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
