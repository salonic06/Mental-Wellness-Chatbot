"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, type Summary, type Patterns, type MoodPoint } from "@/lib/api";
import { MoodChart } from "@/components/MoodChart";
import { VentChart } from "@/components/VentChart";

const STORAGE_KEY = "wellness_dashboard_key";

export default function DashboardPage() {
  const router = useRouter();
  const [apiKey, setApiKey] = useState("");
  const [summary, setSummary] = useState<Summary | null>(null);
  const [moodSeries, setMoodSeries] = useState<MoodPoint[]>([]);
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
      const [s, mood, cats, vent, pat] = await Promise.all([
        api.summary(apiKey),
        api.moodTrends(apiKey),
        api.categories(apiKey),
        api.ventSentiment(apiKey),
        api.patterns(apiKey),
      ]);
      setSummary(s);
      setMoodSeries(mood.series);
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
  }, [apiKey]);

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
          <p className="subtitle">Aggregated signals — no private message text stored.</p>
        </div>
        <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
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
          Last updated {lastRefresh.toLocaleTimeString()}
        </p>
      )}

      {error && <div className="error">{error}</div>}

      {isEmpty && (
        <div className="card" style={{ marginBottom: "1rem", borderColor: "var(--warn)" }}>
          <h3 style={{ marginTop: 0 }}>No data yet</h3>
          {ephemeral ? (
            <p style={{ marginBottom: "0.5rem" }}>
              Your bot is on <strong>Render free tier</strong> with ephemeral SQLite — the database
              resets when the service redeploys or restarts.
            </p>
          ) : postgres ? (
            <p style={{ marginBottom: "0.5rem" }}>
              Connected to <strong>Neon Postgres</strong> — data persists, but nothing logged yet.
            </p>
          ) : (
            <p style={{ marginBottom: "0.5rem" }}>
              The database is empty or was recently reset.
            </p>
          )}
          <ul style={{ margin: 0, paddingLeft: "1.1rem", color: "var(--muted)" }}>
            <li>
              <strong>Conversation tone</strong> fills from free-text chat (vent mode).
            </li>
            <li>
              <strong>Mood chart &amp; check-in topics</strong> need <code>/checkin</code> or{" "}
              <code>/mood 7 note</code> on WhatsApp.
            </li>
            {ephemeral && (
              <li>
                For persistence, switch to <code>render.with-disk.yaml</code> (Starter + 1 GB disk,
                ~$7/mo + $0.25) — see <code>DEPLOY.md</code>.
              </li>
            )}
          </ul>
        </div>
      )}

      {summary && !isEmpty && summary.vent_events > 0 && summary.checkins === 0 && (
        <div className="card" style={{ marginBottom: "1rem" }}>
          <p style={{ margin: 0, color: "var(--muted)" }}>
            Chat conversations are logged under <strong>Conversation tone</strong>. Use{" "}
            <code>/checkin</code> on WhatsApp to populate mood charts and topics.
          </p>
        </div>
      )}

      {summary && (
        <div className="grid grid-4" style={{ marginBottom: "1rem" }}>
          <div className="card">
            <div className="metric-value">{summary.avg_mood_intensity ?? "—"}</div>
            <div className="metric-label">Avg mood (all time)</div>
          </div>
          <div className="card">
            <div className="metric-value">{summary.checkins}</div>
            <div className="metric-label">Check-ins</div>
          </div>
          <div className="card">
            <div className="metric-value">{summary.vent_events}</div>
            <div className="metric-label">Conversations logged</div>
          </div>
          <div className="card">
            <div className="metric-value">{summary.activity_last_7d}</div>
            <div className="metric-label">Activity (7 days)</div>
          </div>
        </div>
      )}

      <div className="grid grid-2">
        <div className="card">
          <h3 style={{ marginTop: 0 }}>Mood over time</h3>
          <MoodChart data={moodSeries} />
        </div>
        <div className="card">
          <h3 style={{ marginTop: 0 }}>Conversation tone</h3>
          <p style={{ color: "var(--muted)", fontSize: "0.85rem" }}>
            VADER sentiment buckets from chat — themes only, not quotes.
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
            <p style={{ color: "var(--muted)" }}>
              Patterns appear after a few check-ins or chat sessions.
            </p>
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
    </main>
  );
}
