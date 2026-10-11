import { useEffect, useState } from "react";
import { get, post } from "../lib/api";

interface OpenSurvey { id: number; title: string; question: string; answered: boolean }

/** One-question member survey shown on the songs page. Answers are stored without names. */
export default function SurveyCard() {
  const [surveys, setSurveys] = useState<OpenSurvey[]>([]);
  const [score, setScore] = useState<number | null>(null);
  const [comment, setComment] = useState("");
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    get<OpenSurvey[]>("/api/surveys/open").then(setSurveys).catch(() => setSurveys([]));
  }, []);
  const s = surveys.find((x) => !x.answered);
  if (done) return <section className="card"><p>Thank you! Your answer was saved without your name.</p></section>;
  if (!s) return null;
  return (
    <section className="card stack tight">
      <h2>{s.question}</h2>
      <div className="scale" role="radiogroup" aria-label="Score from 0 to 10">
        {Array.from({ length: 11 }, (_, i) => (
          <button key={i} role="radio" aria-checked={score === i} className={score === i ? "on" : ""} onClick={() => setScore(i)}>{i}</button>
        ))}
      </div>
      <label>Anything you'd like to add? (optional)
        <textarea id="survey_comment" value={comment} maxLength={1000} onChange={(e) => setComment(e.target.value)} />
      </label>
      <p className="small muted">Your answer is saved without your name. The app only notes that you answered, so you aren't asked twice.</p>
      {error && <p className="error">{error}</p>}
      <button className="primary" disabled={score === null} onClick={() =>
        post(`/api/surveys/${s.id}/answer`, { score, comment }).then(() => setDone(true)).catch((e) => setError(e.message))
      }>Send answer</button>
    </section>
  );
}
