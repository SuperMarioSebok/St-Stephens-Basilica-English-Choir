import { useCallback, useEffect, useState } from "react";
import { ApiError, get, post, type Me } from "./lib/api";
import Login from "./pages/Login";
import Songs from "./pages/Songs";
import Player from "./pages/Player";
import Editor from "./pages/Editor";
import Review from "./pages/Review";
import Feedback from "./pages/Feedback";
import FeedbackList from "./pages/FeedbackList";
import Upload from "./pages/Upload";
import History from "./pages/History";
import Join from "./pages/Join";
import EventPage, { CancelPage } from "./pages/EventPage";
import InvitePage from "./pages/InvitePage";
import Community from "./pages/Community";

// Hash routes keep every page on one server URL: #/play/12, #/edit/12 ...
function useRoute(): string[] {
  const read = () => window.location.hash.replace(/^#\/?/, "").split("?")[0].split("/").filter(Boolean);
  const [route, setRoute] = useState(read);
  useEffect(() => {
    const on = () => setRoute(read());
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return route;
}

export function go(path: string) {
  window.location.hash = path;
}

export default function App() {
  const [me, setMe] = useState<Me | null | undefined>(undefined);
  const route = useRoute();

  const loadMe = useCallback(() => {
    get<Me>("/api/me")
      .then(setMe)
      .catch((e) => {
        if (e instanceof ApiError && e.status === 401) setMe(null);
        else setMe(null);
      });
  }, []);
  useEffect(loadMe, [loadMe]);

  const [page, arg] = route;
  const id = Number(arg);

  // Public pages work without logging in.
  if (page === "join") return <Join />;
  if (page === "event" && id) return <EventPage eventId={id} />;
  if (page === "cancel" && arg) return <CancelPage code={arg} />;
  if (page === "invite" && arg) return <InvitePage token={arg} onJoined={loadMe} />;

  if (me === undefined) return <main className="page"><p>Loading…</p></main>;
  if (me === null) return <Login onLoggedIn={loadMe} />;

  let content;
  if (page === "play" && id) content = <Player versionId={id} me={me} />;
  else if (page === "edit" && id) content = <Editor versionId={id} me={me} />;
  else if (page === "review" && id) content = <Review versionId={id} me={me} />;
  else if (page === "history" && id) content = <History songId={id} />;
  else if (page === "feedback") content = <Feedback songId={id || undefined} />;
  else if (page === "inbox") content = <FeedbackList />;
  else if (page === "upload") content = <Upload />;
  else if (page === "community") content = <Community me={me} />;
  else content = <Songs me={me} />;

  return (
    <>
      <header className="topbar">
        <a href="#/" className="brand">Basilica Voice Coach</a>
        <span className="who">
          {me.display_name}
          <button
            className="link"
            onClick={() => post("/api/logout").finally(() => setMe(null))}
          >
            Log out
          </button>
        </span>
      </header>
      <main className="page">{content}</main>
    </>
  );
}
