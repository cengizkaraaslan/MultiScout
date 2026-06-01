const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const CACHE_KEY = "multiscout_ai_summaries";
const CACHE_TTL = 24 * 60 * 60 * 1000;

interface CacheEntry { summary: string; ts: number }

function readCache(): Record<string, CacheEntry> {
  if (typeof window === "undefined") return {};
  try {
    return JSON.parse(localStorage.getItem(CACHE_KEY) || "{}");
  } catch {
    return {};
  }
}

function writeCache(c: Record<string, CacheEntry>) {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(CACHE_KEY, JSON.stringify(c));
  } catch {
    /* quota */
  }
}

let aiAvailable: boolean | null = null;

export async function checkAiAvailable(): Promise<boolean> {
  if (aiAvailable !== null) return aiAvailable;
  try {
    const res = await fetch(`${API_URL}/api/ai-summary/status`);
    if (!res.ok) {
      aiAvailable = false;
      return false;
    }
    const data = await res.json();
    aiAvailable = !!data.available;
    return aiAvailable;
  } catch {
    aiAvailable = false;
    return false;
  }
}

export async function getAiSummary(deal: { link?: string; title?: string; price?: string; discount_percentage?: number; platform?: string; price_history?: unknown[] }): Promise<{ ok: boolean; summary?: string; error?: string }> {
  if (!deal.link || !deal.title) return { ok: false, error: "missing link/title" };

  const cache = readCache();
  const entry = cache[deal.link];
  if (entry && Date.now() - entry.ts < CACHE_TTL) {
    return { ok: true, summary: entry.summary };
  }

  try {
    const res = await fetch(`${API_URL}/api/ai-summary`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(deal),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      return { ok: false, error: err.detail || `HTTP ${res.status}` };
    }
    const data = await res.json();
    if (data.ok && data.summary) {
      cache[deal.link] = { summary: data.summary, ts: Date.now() };
      writeCache(cache);
      return { ok: true, summary: data.summary };
    }
    return { ok: false, error: data.error || "no summary" };
  } catch (e) {
    return { ok: false, error: String(e) };
  }
}
