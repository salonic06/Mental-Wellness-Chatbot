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

export type ActivityPoint = { day: string; events: number };

export function ActivityChart({ data }: { data: ActivityPoint[] }) {
  if (!data.length) {
    return (
      <p style={{ color: "var(--muted)" }}>
        Activity appears when users check in or chat — try /checkin on WhatsApp.
      </p>
    );
  }
  const chartData = data.map((d) => ({
    day: d.day.slice(5),
    events: d.events,
  }));
  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={chartData}>
        <CartesianGrid stroke="#2a3444" strokeDasharray="3 3" />
        <XAxis dataKey="day" tick={{ fill: "#8b9bb0", fontSize: 10 }} />
        <YAxis allowDecimals={false} tick={{ fill: "#8b9bb0", fontSize: 11 }} />
        <Tooltip
          contentStyle={{
            background: "#151b24",
            border: "1px solid #2a3444",
            borderRadius: 8,
          }}
        />
        <Bar dataKey="events" fill="#a78bfa" radius={[4, 4, 0, 0]} name="Events" />
      </BarChart>
    </ResponsiveContainer>
  );
}
