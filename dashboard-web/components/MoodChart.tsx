"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
import type { MoodPoint } from "@/lib/api";

export function MoodChart({ data }: { data: MoodPoint[] }) {
  if (!data.length) {
    return <p style={{ color: "var(--muted)" }}>No mood data yet — try /checkin on WhatsApp.</p>;
  }
  return (
    <ResponsiveContainer width="100%" height={260}>
      <LineChart data={data}>
        <CartesianGrid stroke="#2a3444" strokeDasharray="3 3" />
        <XAxis dataKey="day" tick={{ fill: "#8b9bb0", fontSize: 11 }} />
        <YAxis domain={[1, 10]} tick={{ fill: "#8b9bb0", fontSize: 11 }} />
        <Tooltip
          contentStyle={{
            background: "#151b24",
            border: "1px solid #2a3444",
            borderRadius: 8,
          }}
        />
        <Line
          type="monotone"
          dataKey="avg_intensity"
          stroke="#6ee7b7"
          strokeWidth={2}
          dot={{ r: 3, fill: "#6ee7b7" }}
          name="Avg mood"
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
