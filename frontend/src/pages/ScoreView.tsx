import { useEffect, useRef, useState } from "react";
import { assetUrl, type Asset } from "../lib/api";

// Renders the version's canonical MusicXML (generated from the same model as the audio)
// with OpenSheetMusicDisplay, loaded only when the score is shown.
export default function ScoreView({ assets }: { assets: Asset[] }) {
  const box = useRef<HTMLDivElement>(null);
  const [state, setState] = useState("Loading score…");
  const score = assets.find((a) => a.kind === "score");

  useEffect(() => {
    if (!score || !box.current) return;
    let cancelled = false;
    (async () => {
      try {
        const [{ OpenSheetMusicDisplay }, xml] = await Promise.all([
          import("opensheetmusicdisplay"),
          fetch(assetUrl(score.id), { credentials: "same-origin" }).then((r) => {
            if (!r.ok) throw new Error(`Score not available (${r.status})`);
            return r.text();
          }),
        ]);
        if (cancelled || !box.current) return;
        box.current.innerHTML = "";
        const osmd = new OpenSheetMusicDisplay(box.current, {
          autoResize: true,
          drawTitle: true,
          drawPartNames: true,
          drawMeasureNumbers: true,
          measureNumberInterval: 1,
          backend: "svg",
        });
        await osmd.load(xml);
        osmd.render();
        setState("");
      } catch (e) {
        setState(`Could not show the score: ${(e as Error).message}`);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [score?.id]);

  if (!score) return <p className="muted">No score display for this version.</p>;
  return (
    <div className="score">
      {state && <p className="muted">{state}</p>}
      <div ref={box} />
    </div>
  );
}
