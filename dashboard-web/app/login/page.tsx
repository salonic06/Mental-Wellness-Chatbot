"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

const STORAGE_KEY = "wellness_dashboard_key";

export default function LoginPage() {
  const router = useRouter();
  const botUrl =
    process.env.NEXT_PUBLIC_API_URL || "https://mental-wellness-bot-d0pv.onrender.com";
  const [apiKey, setApiKey] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await fetch("/api/proxy/metrics/summary", {
        headers: { "X-Dashboard-Key": apiKey, Accept: "application/json" },
      });
      if (res.status === 401) {
        throw new Error(
          "Wrong API key. Copy DASHBOARD_API_KEY exactly from Render → Environment."
        );
      }
      if (!res.ok) {
        let detail = "Could not reach the bot.";
        try {
          const json = await res.json();
          detail = json.error || detail;
        } catch {
          /* ignore */
        }
        throw new Error(detail);
      }
      sessionStorage.setItem(STORAGE_KEY, apiKey);
      router.push("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Connection failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="login-wrap">
      <form className="card login-card" onSubmit={onSubmit}>
        <h1 style={{ marginTop: 0 }}>Wellness dashboard</h1>
        <p className="subtitle" style={{ marginBottom: "1.25rem" }}>
          Your API key stays in this browser only. Data is fetched server-side via
          Vercel (no CORS issues).
        </p>
        <div style={{ marginBottom: "1rem" }}>
          <label>Bot API (configured on Vercel)</label>
          <p style={{ margin: "0.35rem 0 0", fontSize: "0.9rem", wordBreak: "break-all" }}>
            {botUrl}
          </p>
        </div>
        <div style={{ marginBottom: "1rem" }}>
          <label htmlFor="key">Dashboard API key</label>
          <input
            id="key"
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder="Same as DASHBOARD_API_KEY on Render"
            required
          />
        </div>
        {error && (
          <div className="error" style={{ marginBottom: "1rem" }}>
            {error}
          </div>
        )}
        <button type="submit" disabled={loading}>
          {loading ? "Connecting…" : "Connect"}
        </button>
      </form>
    </div>
  );
}
