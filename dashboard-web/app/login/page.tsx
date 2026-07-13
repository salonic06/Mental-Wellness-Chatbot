"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

const STORAGE_KEY = "wellness_dashboard_key";

export default function LoginPage() {
  const router = useRouter();
  const [apiUrl, setApiUrl] = useState(
    process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000"
  );
  const [apiKey, setApiKey] = useState("");
  const [error, setError] = useState("");

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      const res = await fetch(`${apiUrl.replace(/\/$/, "")}/api/metrics/summary`, {
        headers: { "X-Dashboard-Key": apiKey, Accept: "application/json" },
      });
      if (!res.ok) throw new Error("Invalid API URL or dashboard key");
      sessionStorage.setItem(STORAGE_KEY, apiKey);
      sessionStorage.setItem("wellness_api_url", apiUrl);
      router.push("/");
    } catch {
      setError("Could not connect. Check bot URL and DASHBOARD_API_KEY.");
    }
  }

  return (
    <div className="login-wrap">
      <form className="card login-card" onSubmit={onSubmit}>
        <h1 style={{ marginTop: 0 }}>Wellness dashboard</h1>
        <p className="subtitle" style={{ marginBottom: "1.25rem" }}>
          Connect to your Render bot API. Keys stay in this browser only.
        </p>
        <div style={{ marginBottom: "1rem" }}>
          <label htmlFor="url">Bot API URL</label>
          <input
            id="url"
            value={apiUrl}
            onChange={(e) => setApiUrl(e.target.value)}
            placeholder="https://your-bot.onrender.com"
          />
        </div>
        <div style={{ marginBottom: "1rem" }}>
          <label htmlFor="key">Dashboard API key</label>
          <input
            id="key"
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder="Same as DASHBOARD_API_KEY on Render"
          />
        </div>
        {error && <div className="error" style={{ marginBottom: "1rem" }}>{error}</div>}
        <button type="submit">Connect</button>
      </form>
    </div>
  );
}
