"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  api,
  type Summary,
  type Patterns,
  type MoodPoint,
  type ActivityTrends,
} from "@/lib/api";
import { MoodChart } from "@/components/MoodChart";
import { VentChart } from "@/components/VentChart";
import { ActivityChart } from "@/components/ActivityChart";

const STORAGE_KEY = "wellness_dashboard_key";
const RANGE_OPTIONS = [7, 30, 90] as const;

export default function DashboardPage() {
  const router = useRouter();
  const [apiKey, setApiKey] = useState("");
  const [days, setDays] = useState<number>(30);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [moodSeries, setMoodSeries] = useState<MoodPoint[]>([]);
  const [activity, setActivity] = useState<ActivityTrends | null>(null);
  const [categories, setCategories] = useState<{ category: string; count: number }[]>([]);
  const [ventBuckets, setVentBuckets] = useState<{ sentiment_bucket: string; count: number }[]>([]);
  const [patterns, setPatterns] = useState<Patterns | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);

  useEffect(() => {
    const saved = sessionStorage.getItem(STORAGE_KEY);
    if (!saved) {
      router.replace("/login");
      return;
    }
    setApiKey(saved);
  }, [router]);

  const loadData = useCallback(async () => {
    if (!apiKey) return;
    setLoading(true);
    try {
      const [s, mood, act, cats, vent, pat] = await Promise.all([
        api.summary(apiKey),
        api.moodTrends(apiKey, days),
        api.activityTrends(apiKey, days),
        api.categories(apiKey),
        api.ventSentiment(apiKey, days),
        api.patterns(apiKey, days),
      ]);
      setSummary(s);
      setMoodSeries(mood.series);
      setActivity(act);
      setCategories(cats.items);
      setVentBuckets(vent.buckets);
      setPatterns(pat);
      setError("");
      setLastRefresh(new Date());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, [apiKey, days]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  function logout() {
    sessionStorage.removeItem(STORAGE_KEY);
    router.push("/login");
  }

  if (!apiKey) return null;

  const isEmpty =
    summary &&
    summary.checkins === 0 &&
    summary.mood_logs === 0 &&
    summary.vent_events === 0 &&
    summary.activity_last_7d === 0;

  const ephemeral = summary?.storage === "ephemeral";
  const postgres = summary?.storage === "postgres";

  return (
    <main>
      <header className="bar">
        <div>
          <h1>Wellness insights</h1>
          <p className="subtitle">
            Beta cohort — aggregated, anonymous (no message text or phone numbers).
          </p>
        </div>
        <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", flexWrap: "wrap" }}>
          <div className="range-pills" role="group" aria-label="Date range">
            {RANGE_OPTIONS.map((d) => (
              <button
                key={d}
                type="button"
                className={d === days ? "pill active" : "pill"}
                onClick={() => setDays(d)}
              >
                {d}d
              </button>
            ))}
          </div>
          <button type="button" className="secondary" onClick={loadData} disabled={loading}>
            {loading ? "Refreshing…" : "Refresh"}
          </button>
          <button type="button" className="secondary" onClick={logout}>
            Sign out
          </button>
        </div>
      </header>

      {lastRefresh && (
        <p style={{ color: "var(--muted)", fontSize: "0.85rem", marginTop: 0 }}>
          Last updated {lastRefresh.toLocaleTimeString()} · showing last {days} days
        </p>
      )}

      {error && <div className="error">{error}</div>}

      {summary && !isEmpty && (
        <div className="card hero" style={{ marginBottom: "1rem" }}>
          <p className="hero-label">Beta snapshot</p>
          <p className="hero-text">
            <strong>{summary.users}</strong> registered user
            {summary.users === 1 ? "" : "s"}
            {activity ? (
              <>
                {" "}
                · <strong>{activity.active_users}</strong> active in last {days} days ·{" "}
                <strong>{activity.total_events}</strong> logged events
              </>
            ) : null}
            {patterns?.avg_mood != null ? (
              <>
                {" "}
                · avg mood <strong>{patterns.avg_mood}/10</strong>
              </>
            ) : null}
          </p>
          <p style={{ color: "var(--muted)", fontSize: "0.85rem", margin: "0.5rem 0 0" }}>
            Good for interviews: real WhatsApp usage, privacy-safe aggregates, crisis flags only as
            counts.
          </p>
        </div>
      )}

      {isEmpty && (
        <div className="card" style={{ marginBottom: "1rem", borderColor: "var(--warn)" }}>
          <h3 style={{ marginTop: 0 }}>No data yet</h3>
          {ephemeral ? (
            <p style={{ marginBottom: "0.5rem" }}>
              Render free tier may reset SQLite. Use Neon <code>DATABASE_URL</code> for persistence.
            </p>
          ) : postgres ? (
            <p style={{ marginBottom: "0.5rem" }}>
              Neon Postgres connected — ask testers to send <code>/checkin</code>.
            </p>
          ) : (
            <p style={{ marginBottom: "0.5rem" }}>Database is empty or was recently reset.</p>
          )}
        </div>
      )}

      {summary && (
        <div className="grid grid-4" style={{ marginBottom: "1rem" }}>
          <div className="card">
            <div className="metric-value">{summary.users}</div>
            <div className="metric-label">Registered users</div>
          </div>
          <div className="card">
            <div className="metric-value">{summary.checkins}</div>
            <div className="metric-label">Check-ins (all time)</div>
          </div>
          <div className="card">
            <div className="metric-value">{summary.vent_events}</div>
            <div className="metric-label">Chat sessions logged</div>
          </div>
          <div className="card">
            <div className="metric-value">{activity?.total_events ?? summary.activity_last_7d}</div>
            <div className="metric-label">Events ({days} days)</div>
          </div>
        </div>
      )}

      <div className="card" style={{ marginBottom: "1rem" }}>
        <h3 style={{ marginTop: 0 }}>Daily activity</h3>
        <p style={{ color: "var(--muted)", fontSize: "0.85rem", marginTop: 0 }}>
          Check-ins + mood logs + chat tone entries per day (all users combined).
        </p>
        <ActivityChart data={activity?.series ?? []} />
      </div>

      <div className="grid grid-2">
        <div className="card">
          <h3 style={{ marginTop: 0 }}>Mood over time</h3>
          <MoodChart data={moodSeries} />
        </div>
        <div className="card">
          <h3 style={{ marginTop: 0 }}>Conversation tone</h3>
          <p style={{ color: "var(--muted)", fontSize: "0.85rem" }}>
            Sentiment buckets — themes only, not quotes.
          </p>
          <VentChart buckets={ventBuckets} />
        </div>
      </div>

      <div className="grid grid-2" style={{ marginTop: "1rem" }}>
        <div className="card">
          <h3 style={{ marginTop: 0 }}>Check-in topics</h3>
          {!categories.length ? (
            <p style={{ color: "var(--muted)" }}>No categories yet.</p>
          ) : (
            <ul style={{ margin: 0, paddingLeft: "1.1rem" }}>
              {categories.map((c) => (
                <li key={c.category} style={{ marginBottom: "0.35rem" }}>
                  <strong>{c.category}</strong> — {c.count}
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="card">
          <h3 style={{ marginTop: 0 }}>Pattern insights</h3>
          {!patterns?.insights?.length ? (
            <p style={{ color: "var(--muted)" }}>Insights appear after a few check-ins.</p>
          ) : (
            patterns.insights.map((line) => (
              <div className="insight" key={line}>
                {line}
              </div>
            ))
          )}
          {patterns && patterns.crisis_events > 0 && (
            <p style={{ color: "var(--warn)", marginTop: "1rem" }}>
              {patterns.crisis_events} crisis safety flag(s) in the last {patterns.days} days.
            </p>
          )}
        </div>
      </div>

      <p style={{ color: "var(--muted)", fontSize: "0.75rem", marginTop: "1.5rem" }}>
        Dashboard v2 · activity trends + beta snapshot
      </p>
    </main>
  );
}
