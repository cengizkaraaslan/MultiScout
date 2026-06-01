"use client";

import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";

interface PriceHistoryEntry {
  date: string;
  price: string;
  discount_percentage: number;
}

const parsePrice = (p: string): number => {
  const m = p.match(/\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2}|\d+/);
  if (!m) return 0;
  return parseFloat(m[0].replace(/\./g, "").replace(",", "."));
};

const formatDate = (iso: string) => {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso.slice(0, 10);
  return d.toLocaleDateString("tr-TR", { day: "2-digit", month: "2-digit" });
};

export default function PriceHistoryChart({ history }: { history: PriceHistoryEntry[] }) {
  if (!history || history.length === 0) {
    return <div className="text-xs text-gray-400 dark:text-gray-500 px-2 py-3">Fiyat geçmişi yok</div>;
  }

  const data = history
    .map((h) => ({
      date: formatDate(h.date),
      price: parsePrice(h.price),
      discount: h.discount_percentage,
    }))
    .filter((d) => d.price > 0);

  if (data.length === 0) {
    return <div className="text-xs text-gray-400 dark:text-gray-500 px-2 py-3">Fiyat geçmişi yok</div>;
  }

  const min = Math.min(...data.map((d) => d.price));
  const max = Math.max(...data.map((d) => d.price));
  const range = max - min;
  const yDomain: [number, number] = [Math.max(0, min - range * 0.1), max + range * 0.1];

  return (
    <div className="w-full h-32">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 5, right: 5, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(156,163,175,0.2)" />
          <XAxis dataKey="date" tick={{ fontSize: 10 }} stroke="currentColor" />
          <YAxis domain={yDomain} tick={{ fontSize: 10 }} stroke="currentColor" width={40} />
          <Tooltip
            contentStyle={{
              background: "rgba(17,24,39,0.95)",
              border: "none",
              borderRadius: 8,
              color: "white",
              fontSize: 12,
            }}
            labelStyle={{ color: "#fbbf24" }}
            formatter={(value: number) => [`${value.toLocaleString("tr-TR")} TL`, "Fiyat"]}
          />
          <Line
            type="monotone"
            dataKey="price"
            stroke="#f97316"
            strokeWidth={2}
            dot={{ r: 3, fill: "#f97316" }}
            activeDot={{ r: 5 }}
            isAnimationActive
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
