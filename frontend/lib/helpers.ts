export function parsePrice(p: string | undefined | null): number {
  if (!p) return 0;
  const m = p.match(/\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2}|\d+\.\d{2}|\d+/);
  if (!m) return 0;
  let raw = m[0];
  if (raw.includes(",")) raw = raw.replace(/\./g, "").replace(",", ".");
  const f = parseFloat(raw);
  return Number.isFinite(f) ? f : 0;
}

export interface PriceHistoryEntry {
  date: string;
  price: string;
  discount_percentage: number;
}

export type Trend = "up" | "down" | "flat";

export function computeTrend(history: PriceHistoryEntry[] | undefined, fallback: string | undefined): Trend {
  if (!history || history.length < 2) return "flat";
  const current = parsePrice(fallback) || parsePrice(history[history.length - 1]?.price);
  if (!current) return "flat";
  const prev = parsePrice(history[Math.max(0, history.length - 2)]?.price);
  if (!prev) return "flat";
  const diff = (current - prev) / prev;
  if (diff > 0.02) return "up";
  if (diff < -0.02) return "down";
  return "flat";
}

export function extractBrand(title: string): string {
  if (!title) return "";
  // Tipik olarak başlığın ilk kelimesi markadır
  const cleaned = title.replace(/[®™©]/g, "").trim();
  const first = cleaned.split(/\s+/)[0] || "";
  // Çok kısa ya da numeric ise atla
  if (first.length < 2 || /^\d/.test(first)) return "";
  return first;
}

export function toCsv(rows: Record<string, unknown>[]): string {
  if (rows.length === 0) return "";
  const headers = Object.keys(rows[0]);
  const escape = (v: unknown) => {
    const s = v == null ? "" : String(v);
    if (s.includes('"') || s.includes(",") || s.includes("\n")) {
      return `"${s.replace(/"/g, '""')}"`;
    }
    return s;
  };
  const lines = [headers.join(",")];
  for (const r of rows) {
    lines.push(headers.map((h) => escape(r[h])).join(","));
  }
  return lines.join("\n");
}

export function downloadCsv(filename: string, csv: string) {
  if (typeof window === "undefined") return;
  const blob = new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
