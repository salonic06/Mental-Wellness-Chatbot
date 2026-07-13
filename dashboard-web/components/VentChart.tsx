"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
import type { VentBucket } from "@/lib/api";

const LABELS: Record<string, string> = {
  strong_negative: "Heavy",
  mild_negative: "Low",
  neutral: "Mixed",
  mild_positive: "Light +",
  strong_positive: "Bright +",
};

export function VentChart({ buckets }: { buckets: VentBucket[] }) {
  const data = buckets.map((b) => ({
    name: LABELS[b.sentiment_bucket] || b.sentiment_bucket,
    count: b.count,
  }));
  if (!data.length) {
    return <p style={{ color: "var(--muted)" }}>No conversation tone data yet.</p>;
  }
  return (
    <ResponsiveContainer width="100%" height={240}>
      <BarChart data={data}>
        <CartesianGrid stroke="#2a3444" strokeDasharray="3 3" />
        <XAxis dataKey="name" tick={{ fill: "#8b9bb0", fontSize: 11 }} />
        <YAxis allowDecimals={false} tick={{ fill: "#8b9bb0", fontSize: 11 }} />
        <Tooltip
          contentStyle={{
            background: "#151b24",
            border: "1px solid #2a3444",
            borderRadius: 8,
          }}
        />
        <Bar dataKey="count" fill="#7dd3fc" radius={[6, 6, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
