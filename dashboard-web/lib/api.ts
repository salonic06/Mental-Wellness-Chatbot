const DEFAULT_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

function apiBase(): string {
  if (typeof window !== "undefined") {
    return sessionStorage.getItem("wellness_api_url") || DEFAULT_BASE;
  }
  return DEFAULT_BASE;
}

export type Summary = {
  users: number;
  mood_logs: number;
  checkins: number;
  vent_events: number;
  avg_mood_intensity: number | null;
  activity_last_7d: number;
  crisis_flags_vent_table: number;
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

async function get<T>(path: string, apiKey: string): Promise<T> {
  const res = await fetch(`${apiBase()}${path}`, {
    headers: headers(apiKey),
    cache: "no-store",
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status}: ${text.slice(0, 200)}`);
  }
  return res.json();
}

export const api = {
  summary: (key: string) => get<Summary>("/api/metrics/summary", key),
  moodTrends: (key: string, days = 30) =>
    get<{ series: MoodPoint[] }>(`/api/metrics/mood-trends?days=${days}`, key),
  categories: (key: string) =>
    get<{ items: CategoryRow[] }>("/api/metrics/checkin-categories", key),
  ventSentiment: (key: string, days = 30) =>
    get<{ buckets: VentBucket[]; crisis_events: number }>(
      `/api/vent/sentiment-summary?days=${days}`,
      key
    ),
  patterns: (key: string) => get<Patterns>("/api/patterns/insights", key),
};
