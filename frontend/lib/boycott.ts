// Boykot listesi: backend'den çekilir, localStorage'da cache'lenir,
// network başarısızsa embedded fallback kullanılır.
//
// Backend kaynak sırası:
//   1. BOYCOTT_BRANDS_URL env (örn. raw.githubusercontent.com/.../brands.json)
//   2. backend/data/boycott_brands.json (lokal yapılandırılmış liste)
//
// Frontend cache: localStorage anahtarı `boycott_v2`, TTL 24 saat.

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const CACHE_KEY = "boycott_v2";
const CACHE_TTL_MS = 24 * 60 * 60 * 1000;

interface BoycottPayload {
  version?: string;
  source?: string;
  brands: string[];
  excluded_keywords?: string[];
  fetched_at?: number;
}

// Network yoksa kullanılacak gömülü minimum liste
const EMBEDDED_FALLBACK: BoycottPayload = {
  version: "embedded",
  source: "embedded fallback",
  brands: [
    "coca-cola", "coca cola", "cocacola", "cappy", "meysu", "fanta", "sprite",
    "fuse tea", "fusetea", "pepsi", "lipton", "doritos", "lays", "cheetos",
    "nestle", "nestlé", "nescafe", "kitkat", "knorr", "calvé", "algida",
    "l'oreal", "loreal", "garnier", "maybelline", "dove", "axe", "rexona",
    "ariel", "fairy", "pampers", "always", "gillette", "pantene", "head & shoulders",
    "domestos", "cif", "omo", "yumoş", "colgate", "palmolive",
    "huggies", "kleenex", "starbucks", "mcdonald", "burger king", "kfc", "puma",
  ],
  excluded_keywords: ["axess", "kotonlu", "kokoreç", "lipton bardak"],
};

let _cache: BoycottPayload | null = null;
let _normalizedBrands: string[] = [];
let _excluded: string[] = [];

function applyData(data: BoycottPayload) {
  _cache = data;
  _normalizedBrands = (data.brands || []).map((b) => b.toLowerCase());
  _excluded = (data.excluded_keywords || []).map((b) => b.toLowerCase());
}

function readLocalStorage(): BoycottPayload | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(CACHE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed?.brands || !Array.isArray(parsed.brands)) return null;
    if (typeof parsed._ts !== "number") return null;
    if (Date.now() - parsed._ts > CACHE_TTL_MS) return null;
    return parsed as BoycottPayload;
  } catch {
    return null;
  }
}

function writeLocalStorage(data: BoycottPayload) {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(CACHE_KEY, JSON.stringify({ ...data, _ts: Date.now() }));
  } catch {
    /* quota or denied */
  }
}

// Eager init: embedded fallback always usable
applyData(EMBEDDED_FALLBACK);
const _localCached = readLocalStorage();
if (_localCached) applyData(_localCached);

export async function refreshBoycottList(force: boolean = false): Promise<BoycottPayload> {
  const cached = !force ? readLocalStorage() : null;
  if (cached) {
    applyData(cached);
    return cached;
  }
  try {
    const url = `${API_URL}/api/boycott-brands${force ? "?refresh=true" : ""}`;
    const res = await fetch(url, { cache: force ? "no-store" : "default" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    if (data?.status === "success" && Array.isArray(data.brands)) {
      const payload: BoycottPayload = {
        version: data.version,
        source: data.source,
        brands: data.brands,
        excluded_keywords: data.excluded_keywords || [],
        fetched_at: data.fetched_at,
      };
      applyData(payload);
      writeLocalStorage(payload);
      return payload;
    }
    throw new Error("invalid payload");
  } catch (e) {
    console.warn("[boycott] fetch failed, using fallback:", e);
    return _cache || EMBEDDED_FALLBACK;
  }
}

export function isBoycotted(title: string | undefined | null): string | null {
  if (!title) return null;
  const t = title.toLowerCase();
  for (const ex of _excluded) {
    if (t.includes(ex)) return null;
  }
  for (const brand of _normalizedBrands) {
    if (t.includes(brand)) return brand;
  }
  return null;
}

export function getBoycottMeta(): { version?: string; source?: string; count: number; fetched_at?: number } {
  return {
    version: _cache?.version,
    source: _cache?.source,
    count: _normalizedBrands.length,
    fetched_at: _cache?.fetched_at,
  };
}

// Compat: eski kod `BOYCOTT_BRANDS`'i import ediyorsa çalışmaya devam etsin.
export const BOYCOTT_BRANDS: string[] = EMBEDDED_FALLBACK.brands;
