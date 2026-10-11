import { useEffect, useRef, useState } from "react";
import QRCode from "qrcode";

/** Days, hours and minutes until `target`. Updates every 30 seconds. */
export function Countdown({ target, label }: { target: string; label: string }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = window.setInterval(() => setNow(Date.now()), 30000);
    return () => window.clearInterval(t);
  }, []);
  const ms = new Date(target).getTime() - now;
  if (Number.isNaN(ms) || ms <= 0) return null;
  const days = Math.floor(ms / 86400000);
  const hours = Math.floor((ms % 86400000) / 3600000);
  const minutes = Math.floor((ms % 3600000) / 60000);
  return (
    <div className="countdown" role="timer" aria-label={`${label}: ${days} days ${hours} hours`}>
      <p className="label">{label}</p>
      <div className="row">
        <span><strong>{days}</strong> days</span>
        <span><strong>{hours}</strong> hours</span>
        <span><strong>{minutes}</strong> min</span>
      </div>
    </div>
  );
}

export function formatWhen(iso: string): string {
  try {
    return new Date(iso).toLocaleString("en-GB", {
      weekday: "long", day: "numeric", month: "long", year: "numeric", hour: "2-digit", minute: "2-digit",
      timeZone: "Europe/Budapest",
    });
  } catch {
    return iso;
  }
}

export function formatDate(isoDate: string): string {
  try {
    return new Date(`${isoDate}T12:00:00`).toLocaleDateString("en-GB", {
      weekday: "long", day: "numeric", month: "long",
    });
  } catch {
    return isoDate;
  }
}

/** Share buttons. Each link carries only the channel (?src=whatsapp), never who shared it. */
export function ShareButtons({ text, hash }: { text: string; hash: string }) {
  const [copied, setCopied] = useState(false);
  const link = (src: string) => `${window.location.origin}/?src=${src}#${hash}`;
  const canShare = typeof navigator !== "undefined" && "share" in navigator;
  return (
    <div className="row wrap share">
      {canShare && (
        <button
          className="primary"
          onClick={() => void navigator.share({ title: text, text, url: link("web") }).catch(() => undefined)}
        >
          Share…
        </button>
      )}
      <a className="button" href={`https://wa.me/?text=${encodeURIComponent(`${text} ${link("whatsapp")}`)}`}
        target="_blank" rel="noopener">WhatsApp</a>
      <a className="button" href={`https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(link("facebook"))}`}
        target="_blank" rel="noopener">Facebook</a>
      <button
        onClick={() =>
          navigator.clipboard
            .writeText(link("web"))
            .then(() => setCopied(true))
            .catch(() => setCopied(false))
        }
      >
        {copied ? "Link copied ✓" : "Copy link"}
      </button>
    </div>
  );
}

/** A QR code drawn on a canvas, for posters and cards at the church door. */
export function QR({ value, size = 220 }: { value: string; size?: number }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    if (canvas.current) void QRCode.toCanvas(canvas.current, value, { width: size, margin: 2 });
  }, [value, size]);
  return <canvas ref={canvas} className="qr" aria-label={`QR code for ${value}`} />;
}
