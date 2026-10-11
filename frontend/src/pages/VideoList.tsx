import { useState } from "react";
import { assetUrl, PART_NAMES, type Asset, type Part } from "../lib/api";

const MODE: Record<string, string> = { alone: "alone", louder: "louder" };

function label(a: Asset): string {
  if (a.part === "full") return `Full choir · ${a.tempo}%`;
  const [vp, mode] = (a.part ?? "").split("-");
  return `${PART_NAMES[vp as Part] ?? vp} ${MODE[mode] ?? mode} · ${a.tempo}%`;
}

/** Private practice videos, played in the page; the player's own part is listed first. */
export default function VideoList({ assets, preferPart }: { assets: Asset[]; preferPart?: Part }) {
  const videos = assets
    .filter((a) => a.kind === "video")
    .sort((a, b) => {
      const rank = (x: Asset) => (preferPart && x.part?.startsWith(preferPart) ? 0 : x.part === "full" ? 2 : 1);
      return rank(a) - rank(b) || label(a).localeCompare(label(b));
    });
  const [playing, setPlaying] = useState<string | null>(null);
  if (videos.length === 0) return null;
  return (
    <div className="stack tight">
      {playing && <video key={playing} src={assetUrl(playing)} controls autoPlay playsInline className="practice-video" />}
      <div className="videos">
        {videos.map((v) => (
          <button key={v.id} className={playing === v.id ? "on" : ""} onClick={() => setPlaying(v.id)}>▶ {label(v)}</button>
        ))}
      </div>
    </div>
  );
}
