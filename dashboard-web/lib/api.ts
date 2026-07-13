export type Summary = {
  users: number;
  mood_logs: number;
  checkins: number;
  vent_events: number;
  avg_mood_intensity: number | null;
  activity_last_7d: number;
  crisis_flags_vent_table: number;
  storage?: "persistent" | "ephemeral" | "postgres";
};

export type MoodPoint = { day: string; avg_intensity: number; entries: number };
export type CategoryRow = { category: string; count: number };
export type VentBucket = { sentiment_bucket: string; count: number };
export type Patterns = {
  days: number;
  avg_mood: number | null;
  mood_entries: number;
  top_categories: CategoryRow[];
  vent_tone: Record<string, number>;
  crisis_events: number;
  insights: string[];
};

function headers(apiKey: string): HeadersInit {
  const h: HeadersInit = { Accept: "application/json" };
  if (apiKey) h["X-Dashboard-Key"] = apiKey;
  return h;
}

/** Calls Vercel server proxy → Render bot (no browser CORS). */
async function get<T>(proxyPath: string, apiKey: string): Promise<T> {
  const res = await fetch(`/api/proxy/${proxyPath}`, {
    headers: headers(apiKey),
    cache: "no-store",
  });
  if (!res.ok) {
    let detail = "";
    try {
      const json = await res.json();
      detail = json.error || JSON.stringify(json);
    } catch {
      detail = await res.text();
    }
    if (res.status === 401) {
      throw new Error("Wrong dashboard API key — must match DASHBOARD_API_KEY on Render.");
    }
    throw new Error(detail || `Request failed (${res.status})`);
  }
  return res.json();
}

export const api = {
  summary: (key: string) => get<Summary>("metrics/summary", key),
  moodTrends: (key: string, days = 30) =>
    get<{ series: MoodPoint[] }>(`metrics/mood-trends?days=${days}`, key),
  categories: (key: string) =>
    get<{ items: CategoryRow[] }>("metrics/checkin-categories", key),
  ventSentiment: (key: string, days = 30) =>
    get<{ buckets: VentBucket[]; crisis_events: number }>(
      `vent/sentiment-summary?days=${days}`,
      key
    ),
  patterns: (key: string) => get<Patterns>("patterns/insights", key),
};
