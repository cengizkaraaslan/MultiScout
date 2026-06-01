"use client";

import { useEffect, useMemo, useState } from "react";
import Image from "next/image";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type CampaignKind = "kampanya" | "bogo";

interface Campaign {
  title: string;
  price: string;
  discount_percentage: number;
  link: string;
  image: string;
  category: string;
  platform: string;
  campaign_kind: CampaignKind;
  last_updated: string | null;
}

const PLATFORM_BADGE: Record<string, { label: string; color: string }> = {
  burgerking: { label: "Burger King", color: "from-yellow-500 to-orange-600" },
  mcdonalds: { label: "McDonald's", color: "from-yellow-400 to-red-600" },
  vodafone: { label: "Vodafone", color: "from-red-500 to-red-700" },
  turkcell: { label: "Turkcell", color: "from-yellow-500 to-amber-600" },
  turktelekom: { label: "Türk Telekom", color: "from-blue-600 to-indigo-700" },
  maximum: { label: "Maximum", color: "from-blue-700 to-cyan-700" },
  bonus: { label: "Bonus", color: "from-green-600 to-emerald-700" },
  world: { label: "World", color: "from-violet-600 to-purple-700" },
  axess: { label: "Axess", color: "from-rose-600 to-red-700" },
  a101: { label: "A101", color: "from-red-500 to-rose-600" },
  bim: { label: "BİM", color: "from-rose-500 to-pink-600" },
  sok: { label: "ŞOK", color: "from-amber-500 to-orange-600" },
  migros: { label: "MİGROS", color: "from-orange-500 to-red-500" },
  carrefoursa: { label: "CarrefourSA", color: "from-blue-500 to-cyan-600" },
  tarimkredi: { label: "Tarım Kredi", color: "from-emerald-500 to-green-600" },
  hakmarexpress: { label: "Hakmar Express", color: "from-red-600 to-rose-700" },
  macrocenter: { label: "Macrocenter", color: "from-indigo-500 to-purple-600" },
  bizimtoptan: { label: "Bizim Toptan", color: "from-sky-500 to-blue-600" },
  peynircibaba: { label: "Peynirci Baba", color: "from-amber-500 to-yellow-600" },
};

const CATEGORY_LABEL: Record<string, string> = {
  "1plus1-bedava": "1 Alana 1 Bedava",
  "ikili-firsat": "İkili Fırsat",
  "kombo-menu": "Kombo Menü",
  "cocuk-menusu": "Çocuk Menüsü",
  "kahvalti": "Kahvaltı",
  "kampanya": "Kampanya",
  // Operatör kampanyaları
  "ucretsiz-internet": "Ücretsiz İnternet",
  "gb-hediye": "GB Hediye",
  "ev-interneti": "Ev İnterneti",
  "fiber": "Fiber",
  "faturasiz": "Faturasız",
  "faturali": "Faturalı",
  "mobil-hat": "Mobil Hat",
  "indirim": "İndirim",
  "ucretsiz-hediye": "Ücretsiz Hediye",
  "hediye": "Hediye",
  "marka": "Marka Ayrıcalığı",
  "red-ayricalik": "Red Ayrıcalığı",
  "dijital-servis": "Dijital Servis",
  "prime": "Prime",
  "ek-servis": "Ek Servis",
  "diger": "Diğer",
  // Banka kampanyaları
  "chargeback": "Chargeback / İade",
  "puan": "Puan Kazanımı",
  "maxipuan": "MaxiPuan",
  "worldpuan": "WorldPuan",
  "chip-para": "Chip-Para",
  "bonus": "Bonus",
  "sinema": "Sinema",
  "restoran": "Restoran",
  "market": "Market",
  "seyahat": "Seyahat",
  "taksit": "Taksit",
  "akaryakit": "Akaryakıt",
  "online": "Online Alışveriş",
  "giyim": "Giyim",
  "elektronik": "Elektronik",
  "ev": "Ev",
  "kobi": "KOBİ",
  "spor": "Spor",
  "iade": "İade",
};

type Filter = "all" | "bogo" | "restoran" | "operator" | "banka" | "market";

const RESTORAN_SET = new Set(["burgerking", "mcdonalds"]);
const OPERATOR_SET = new Set(["vodafone", "turkcell", "turktelekom"]);
const BANKA_SET = new Set(["maximum", "bonus", "world", "axess"]);
const MARKET_SET = new Set([
  "a101", "bim", "sok", "migros", "carrefoursa", "tarimkredi",
  "hakmarexpress", "macrocenter", "bizimtoptan", "peynircibaba",
]);

export default function KampanyalarPage() {
  const [items, setItems] = useState<Campaign[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>("all");

  useEffect(() => {
    (async () => {
      setLoading(true);
      setErr(null);
      try {
        const res = await fetch(`${API_URL}/api/campaigns?limit=400`);
        if (!res.ok) {
          setErr(`Sunucu hatası: HTTP ${res.status}`);
          return;
        }
        const data = await res.json();
        if (data.status !== "success") {
          setErr(data.message || "Bilinmeyen hata");
          return;
        }
        setItems((data.data || []) as Campaign[]);
      } catch (e) {
        setErr((e as Error).message);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const visible = useMemo(() => {
    if (filter === "all") return items;
    if (filter === "bogo") return items.filter((c) => c.campaign_kind === "bogo");
    if (filter === "restoran") return items.filter((c) => RESTORAN_SET.has(c.platform));
    if (filter === "operator") return items.filter((c) => OPERATOR_SET.has(c.platform));
    if (filter === "banka") return items.filter((c) => BANKA_SET.has(c.platform));
    if (filter === "market") return items.filter((c) => MARKET_SET.has(c.platform));
    return items;
  }, [items, filter]);

  const counts = useMemo(() => ({
    all: items.length,
    bogo: items.filter((c) => c.campaign_kind === "bogo").length,
    restoran: items.filter((c) => RESTORAN_SET.has(c.platform)).length,
    operator: items.filter((c) => OPERATOR_SET.has(c.platform)).length,
    banka: items.filter((c) => BANKA_SET.has(c.platform)).length,
    market: items.filter((c) => MARKET_SET.has(c.platform)).length,
  }), [items]);

  return (
    <main className="min-h-screen bg-gradient-to-b from-gray-50 to-gray-100 dark:from-gray-950 dark:to-gray-900 text-gray-900 dark:text-gray-100 pb-20">
      <header className="sticky top-0 z-30 bg-white/85 dark:bg-gray-950/85 backdrop-blur-md border-b border-gray-200 dark:border-gray-800">
        <div className="max-w-[1400px] mx-auto px-3 md:px-6 py-3 flex items-center gap-3">
          <a href="/" className="text-base md:text-xl font-bold bg-gradient-to-r from-orange-500 to-red-500 bg-clip-text text-transparent">
            ← MultiScout
          </a>
          <h1 className="text-base md:text-xl font-bold bg-gradient-to-r from-fuchsia-500 to-pink-600 bg-clip-text text-transparent">
            🎁 Kampanyalar
          </h1>
          {!loading && (
            <span className="ml-auto text-xs md:text-sm font-bold text-pink-600 dark:text-pink-400 bg-pink-50 dark:bg-pink-900/30 border border-pink-200 dark:border-pink-700/50 px-2 md:px-3 py-0.5 md:py-1 rounded-full">
              {visible.length} kampanya
            </span>
          )}
        </div>
        <div className="max-w-[1400px] mx-auto px-3 md:px-6 pb-3 flex gap-2 overflow-x-auto">
          {([
            { k: "all", label: "Tümü", icon: "🎯" },
            { k: "bogo", label: "1 Alana 1 Bedava", icon: "🎁" },
            { k: "restoran", label: "Restoran", icon: "🍔" },
            { k: "operator", label: "Operatör", icon: "📱" },
            { k: "banka", label: "Banka", icon: "💳" },
            { k: "market", label: "Market", icon: "🛍️" },
          ] as { k: Filter; label: string; icon: string }[]).map((f) => (
            <button
              key={f.k}
              onClick={() => setFilter(f.k)}
              className={`shrink-0 px-3 py-1.5 rounded-full text-sm font-medium transition whitespace-nowrap ${
                filter === f.k
                  ? "text-white bg-gradient-to-r from-fuchsia-500 to-pink-600 shadow-sm"
                  : "bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-200 border border-gray-200 dark:border-gray-700"
              }`}
            >
              {f.icon} {f.label}
              <span className="ml-1.5 text-xs opacity-75">{counts[f.k]}</span>
            </button>
          ))}
        </div>
      </header>

      <div className="max-w-[1400px] mx-auto px-3 md:px-6 py-6">
        {loading && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="h-64 rounded-2xl bg-gray-200/60 dark:bg-gray-800/60 animate-pulse" />
            ))}
          </div>
        )}

        {err && !loading && (
          <div className="rounded-2xl border border-red-300 dark:border-red-800 bg-red-50 dark:bg-red-900/20 p-4 text-sm text-red-700 dark:text-red-300">
            ⚠ Kampanyalar yüklenemedi: {err}
          </div>
        )}

        {!loading && !err && visible.length === 0 && (
          <div className="rounded-2xl border border-gray-200 dark:border-gray-700 bg-white/60 dark:bg-gray-800/60 p-8 text-center text-gray-500 dark:text-gray-400">
            Bu filtrede henüz kampanya yok.
            <br />
            Manuel tarama için <a href="/" className="text-pink-600 hover:underline">ana sayfada</a> Burger King platformunu seçip taratabilirsin.
          </div>
        )}

        {!loading && !err && visible.length > 0 && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {visible.map((c) => {
              const brand = PLATFORM_BADGE[c.platform] || { label: c.platform, color: "from-gray-500 to-gray-600" };
              const catLabel = CATEGORY_LABEL[c.category] || c.category;
              return (
                <a
                  key={c.link}
                  href={c.link}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="group relative block rounded-2xl overflow-hidden bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 hover:shadow-xl transition-shadow"
                >
                  <div className="relative w-full aspect-[16/10] bg-gray-100 dark:bg-gray-900">
                    {c.image ? (
                      <Image
                        src={c.image}
                        alt={c.title}
                        fill
                        sizes="(min-width:1024px) 33vw, (min-width:640px) 50vw, 100vw"
                        className="object-cover group-hover:scale-105 transition-transform"
                        unoptimized={c.image.startsWith("/cmsfiles")}
                      />
                    ) : (
                      <div className="absolute inset-0 flex items-center justify-center text-gray-400">🖼️</div>
                    )}
                    <span
                      className={`absolute top-2 left-2 px-2 py-0.5 rounded-full text-[11px] font-semibold text-white bg-gradient-to-r ${brand.color} shadow`}
                    >
                      {brand.label}
                    </span>
                    {c.campaign_kind === "bogo" && (
                      <span className="absolute top-2 right-2 px-2 py-0.5 rounded-full text-[11px] font-bold text-white bg-gradient-to-r from-fuchsia-500 to-pink-600 shadow">
                        🎁 1+1
                      </span>
                    )}
                  </div>
                  <div className="p-3">
                    <h3 className="font-semibold text-sm md:text-base line-clamp-2">{c.title}</h3>
                    <div className="mt-2 flex items-center justify-between text-xs">
                      <span className="text-gray-500 dark:text-gray-400">{catLabel}</span>
                      <span className="font-bold text-pink-600 dark:text-pink-400">
                        {c.price === "Kampanya" ? "Detay →" : c.price}
                      </span>
                    </div>
                  </div>
                </a>
              );
            })}
          </div>
        )}
      </div>
    </main>
  );
}
