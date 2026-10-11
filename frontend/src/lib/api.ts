// All calls go to the same origin with the session cookie. State-changing calls carry
// the X-BVC header that the server requires (blocks cross-site form posts).

export type Part = "S" | "A" | "T" | "B";
export const PARTS: Part[] = ["S", "A", "T", "B"];
export const PART_NAMES: Record<Part, string> = { S: "Soprano", A: "Alto", T: "Tenor", B: "Bass" };

export interface Me {
  username: string;
  display_name: string;
  role: "singer" | "voice_lead" | "director";
  voice_part: Part | null;
}

export interface SongItem {
  id: number;
  title: string;
  kind: "score" | "manual";
  is_test_piece: boolean;
  approved_version_id: number | null;
  latest_version_id?: number;
  latest_number?: number;
  latest_status?: string;
  render?: { status: string; error?: string | null; attempts?: number; max_attempts?: number };
  rights_note?: string;
}

export interface Asset {
  id: string;
  kind: "stem" | "mix" | "score" | "source_audio" | "pdf";
  part: string | null;
  tempo: number | null;
  mime: string;
  seconds: number | null;
}

export interface TimelineBar {
  index: number;
  label: string;
  pickup: boolean;
  start: number; // seconds at 100% tempo
}

export interface Flag {
  level: "info" | "warn" | "error";
  code: string;
  message: string;
  part: Part | null;
  bar: number | null;
}

export interface MappingEntry {
  part_id: string | null;
  staff: number | null;
  voice: string | null;
  octave_shift: number;
  confirmed: boolean;
  confirmed_by?: string | null;
  label: string;
}

export interface Stream {
  key: string;
  part_id: string;
  part_name: string;
  staff: number;
  voice: string;
  note_count: number;
  chord_count: number;
  low: number | null;
  high: number | null;
}

export interface VersionDetail {
  id: number;
  song_id: number;
  title: string;
  kind: "score" | "manual";
  number: number;
  status: string;
  assets: Asset[];
  tempos: number[];
  timeline?: { bars: TimelineBar[]; end: number };
  parts?: Record<Part, string | null>;
  cursor_verified?: boolean;
  manual?: { note?: string };
  // staff only
  created_at?: string;
  change_summary?: string;
  review_decision_note?: string | null;
  latest?: boolean;
  render?: { status: string; error?: string | null; attempts?: number; max_attempts?: number };
  readiness?: string[];
  model?: { bars: { index: number; label: string; ticks: number; time: string }[]; tempo: { tick: number; bpm: number }[]; flags: Flag[] };
  mapping?: Record<Part, MappingEntry>;
  bar_tokens?: Record<Part, string[] | null>;
  inventory?: { streams: Stream[]; parts: { id: string; name: string; staves: number }[] };
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function handle<T>(r: Response): Promise<T> {
  if (r.status === 204) return undefined as T;
  const body = await r.json().catch(() => ({}));
  if (!r.ok) {
    const d = (body as { detail?: unknown }).detail;
    const msg = typeof d === "string" ? d : Array.isArray(d) ? "Please check the form fields" : `Error ${r.status}`;
    throw new ApiError(r.status, msg);
  }
  return body as T;
}

export function get<T>(path: string): Promise<T> {
  return fetch(path, { credentials: "same-origin" }).then((r) => handle<T>(r));
}

export function post<T>(path: string, body?: unknown): Promise<T> {
  return fetch(path, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", "X-BVC": "1" },
    body: JSON.stringify(body ?? {}),
  }).then((r) => handle<T>(r));
}

export function postForm<T>(path: string, form: FormData): Promise<T> {
  return fetch(path, { method: "POST", credentials: "same-origin", headers: { "X-BVC": "1" }, body: form }).then(
    (r) => handle<T>(r),
  );
}

export const assetUrl = (id: string) => `/api/assets/${encodeURIComponent(id)}`;
