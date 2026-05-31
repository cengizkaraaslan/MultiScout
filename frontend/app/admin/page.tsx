"use client";
/* eslint-disable react/no-unescaped-entities */

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import { toast } from "sonner";
import {
  adminLogin, adminGetSettings, adminPatchSection,
  getAdminPassword, clearAdminPassword,
} from "../../lib/admin";

type Tab = "dashboard" | "stores" | "scheduler" | "health" | "webhooks" | "backup" | "theme" | "social" | "auto_share" | "boycott" | "maintenance" | "logs" | "docs";

interface SchedulerTier { enabled: boolean; interval_min: number; min_discount: number; platforms: string[] }
interface SchedulerSettings {
  enabled: boolean;
  amazon_interval_min: number;
  other_interval_min: number;
  tiers: Record<string, SchedulerTier>;
}
interface Webhooks { enabled: boolean; min_discount: number; discord_url: string; slack_url: string }

interface Settings {
  stores: Record<string, boolean>;
  theme: { primary: string; accent: string; logo_text: string; tagline: string };
  social: {
    telegram: { enabled: boolean; bot_token: string; chat_id: string };
    instagram: { enabled: boolean; access_token: string; business_account_id: string };
    facebook: { enabled: boolean; page_access_token: string; page_id: string };
  };
  auto_share: { enabled: boolean; min_discount: number; max_per_day: number; platforms: string[] };
  scheduler: SchedulerSettings;
  webhooks: Webhooks;
  maintenance: { enabled: boolean; message: string };
}

const STORE_LABELS: Record<string, string> = {
  amazon: "Amazon", trendyol: "Trendyol", n11: "N11", hepsiburada: "Hepsiburada",
  pazarama: "Pazarama", ciceksepeti: "Çiçek Sepeti", vatan: "Vatan Bilgisayar",
  teknosa: "Teknosa", decathlon: "Decathlon", steam: "Steam",
  mediamarkt: "MediaMarkt", defacto: "Defacto", gratis: "Gratis",
  a101: "A101", bim: "BİM", sok: "ŞOK", migros: "MİGROS",
  carrefoursa: "CarrefourSA", tarimkredi: "Tarım Kredi",
  hakmarexpress: "Hakmar Express", macrocenter: "Macrocenter", bizimtoptan: "Bizim Toptan", peynircibaba: "Peynirci Baba",
  burgerking: "Burger King", mcdonalds: "McDonald's",
  vodafone: "Vodafone", turkcell: "Turkcell", turktelekom: "Türk Telekom",
  maximum: "Maximum", bonus: "Bonus", world: "World", axess: "Axess",
  lcwaikiki: "LC Waikiki", koton: "Koton", mavi: "Mavi",
  boyner: "Boyner", penti: "Penti", watsons: "Watsons", dr: "D&R",
  karaca: "Karaca", englishhome: "English Home", idefix: "Idefix", tchibo: "Tchibo",
  mudo: "Mudo", madamecoco: "Madame Coco", vivense: "Vivense",
  tepehome: "Tepe Home", skechers: "Skechers",
  toyzz: "Toyzz Shop", yargici: "Yargıcı", kitapyurdu: "Kitapyurdu",
  pttavm: "PttAVM", sportive: "Sportive", newbalance: "New Balance",
  flo: "FLO", hummel: "Hummel", evidea: "Evidea",
  beko: "Beko", arcelik: "Arçelik", vestel: "Vestel",
  network: "Network", northface: "The North Face",
  mac: "MAC Cosmetics", apple: "Apple",
  saatvesaat: "Saat ve Saat", altinbas: "Altınbaş", pasabahce: "Paşabahçe",
  akakce: "Akakçe", ramsey: "Ramsey", atasay: "Atasay",
  reebok: "Reebok", sarar: "Sarar", huawei: "Huawei", lego: "Lego",
  casper: "Casper", monster: "Monster",
};

// Mağaza kategori grupları — 64 platformu vertical bazlı toparlar
const STORE_CATEGORIES: { id: string; label: string; icon: string; stores: string[] }[] = [
  { id: "marketplace", label: "Marketplace", icon: "🛒", stores: ["amazon", "trendyol", "n11", "hepsiburada", "pazarama", "ciceksepeti", "pttavm"] },
  { id: "fashion", label: "Moda", icon: "👗", stores: ["lcwaikiki", "koton", "mavi", "defacto", "boyner", "penti", "watsons", "mudo", "network", "yargici", "ramsey", "sarar", "reebok"] },
  { id: "cosmetics", label: "Kozmetik", icon: "💄", stores: ["gratis", "mac"] },
  { id: "home", label: "Ev / Dekorasyon", icon: "🏠", stores: ["karaca", "madamecoco", "vivense", "tepehome", "evidea", "englishhome", "pasabahce"] },
  { id: "electronics", label: "Elektronik & Tech", icon: "💻", stores: ["vatan", "teknosa", "mediamarkt", "beko", "arcelik", "vestel", "apple", "huawei", "casper", "monster"] },
  { id: "books", label: "Kitap", icon: "📚", stores: ["dr", "idefix", "kitapyurdu"] },
  { id: "toys", label: "Oyuncak", icon: "🧸", stores: ["toyzz", "lego"] },
  { id: "sports", label: "Spor", icon: "⚽", stores: ["decathlon", "skechers", "newbalance", "sportive", "hummel", "flo"] },
  { id: "outdoor", label: "Outdoor", icon: "⛰️", stores: ["northface"] },
  { id: "market", label: "Market (Gıda)", icon: "🛍️", stores: ["a101", "bim", "sok", "migros", "carrefoursa", "tarimkredi", "hakmarexpress", "macrocenter", "bizimtoptan", "peynircibaba", "tchibo"] },
  { id: "campaigns_food", label: "Restoran Kampanyaları", icon: "🍔", stores: ["burgerking", "mcdonalds"] },
  { id: "campaigns_telco", label: "Operatör Kampanyaları", icon: "📱", stores: ["vodafone", "turkcell", "turktelekom"] },
  { id: "campaigns_bank", label: "Banka Kampanyaları", icon: "💳", stores: ["maximum", "bonus", "world", "axess"] },
  { id: "niche", label: "Mücevher & Saat", icon: "💎", stores: ["altinbas", "atasay", "saatvesaat"] },
  { id: "comparison", label: "Fiyat Karşılaştırma", icon: "📊", stores: ["akakce"] },
  { id: "games", label: "Oyun", icon: "🎮", stores: ["steam"] },
];

// Tüm kategorize edilmemiş mağazaları "Diğer" altında topla
function getStoreCategory(storeKey: string): string {
  for (const cat of STORE_CATEGORIES) {
    if (cat.stores.includes(storeKey)) return cat.id;
  }
  return "other";
}

const TABS: { id: Tab; label: string; icon: string }[] = [
  { id: "dashboard", label: "Dashboard", icon: "📊" },
  { id: "stores", label: "Mağazalar", icon: "🏪" },
  { id: "scheduler", label: "Tarama", icon: "🔄" },
  { id: "health", label: "Sağlık", icon: "🩺" },
  { id: "webhooks", label: "Webhook", icon: "📡" },
  { id: "backup", label: "Yedek", icon: "💾" },
  { id: "theme", label: "Tema", icon: "🎨" },
  { id: "social", label: "Sosyal Medya", icon: "📱" },
  { id: "auto_share", label: "Otomatik Paylaşım", icon: "🤖" },
  { id: "boycott", label: "Boykot Listesi", icon: "🚫" },
  { id: "maintenance", label: "Bakım Modu", icon: "🚧" },
  { id: "logs", label: "Loglar", icon: "📜" },
  { id: "docs", label: "API Rehberi", icon: "📚" },
];

export default function AdminPage() {
  const [authed, setAuthed] = useState<boolean | null>(null);
  const [password, setPassword] = useState("");
  const [loginErr, setLoginErr] = useState("");
  const [settings, setSettings] = useState<Settings | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>("dashboard");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const pw = getAdminPassword();
    if (!pw) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setAuthed(false);
      return;
    }
    (async () => {
      const s = await adminGetSettings();
      if (s) {
        setSettings(s as unknown as Settings);
        setAuthed(true);
      } else {
        clearAdminPassword();
        setAuthed(false);
      }
    })();
  }, []);

  const handleLogin = async () => {
    setBusy(true);
    setLoginErr("");
    const ok = await adminLogin(password);
    setBusy(false);
    if (!ok) {
      setLoginErr("Şifre yanlış");
      return;
    }
    const s = await adminGetSettings();
    setSettings(s as unknown as Settings);
    setAuthed(true);
    toast.success("Hoş geldin, admin!");
  };

  const handleLogout = () => {
    clearAdminPassword();
    setAuthed(false);
    setSettings(null);
    setPassword("");
    toast.message("Çıkış yapıldı");
  };

  const updateSection = async (section: string, payload: Record<string, unknown>) => {
    setBusy(true);
    const ok = await adminPatchSection(section, payload);
    setBusy(false);
    if (!ok) {
      toast.error("Kaydedilemedi");
      return false;
    }
    const fresh = await adminGetSettings();
    if (fresh) setSettings(fresh as unknown as Settings);
    toast.success("Kaydedildi");
    return true;
  };

  if (authed === null) {
    return (
      <main className="min-h-screen bg-gray-50 dark:bg-gray-950 flex items-center justify-center">
        <div className="text-gray-500 dark:text-gray-400">Yükleniyor...</div>
      </main>
    );
  }

  if (!authed) {
    return (
      <main className="min-h-screen bg-gradient-to-b from-gray-50 to-gray-100 dark:from-gray-950 dark:to-gray-900 flex items-center justify-center px-4">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-white dark:bg-gray-900 rounded-2xl shadow-xl border border-gray-200 dark:border-gray-800 p-8 w-full max-w-sm"
        >
          <div className="text-center mb-6">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-orange-500 to-red-500 text-white text-2xl font-bold flex items-center justify-center mx-auto mb-3">
              🔐
            </div>
            <h1 className="text-xl font-bold text-gray-900 dark:text-gray-100">Admin Girişi</h1>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">MultiScout yönetim paneli</p>
          </div>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleLogin()}
            placeholder="Şifre"
            className="w-full px-4 py-3 rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 text-gray-900 dark:text-white focus:outline-none focus:border-blue-500 mb-3"
          />
          {loginErr && <p className="text-sm text-rose-500 mb-3">{loginErr}</p>}
          <button
            onClick={handleLogin}
            disabled={busy || !password}
            className="w-full px-4 py-3 rounded-lg bg-gradient-to-r from-blue-500 to-blue-600 text-white font-semibold disabled:opacity-50"
          >
            {busy ? "Giriş yapılıyor..." : "Giriş Yap"}
          </button>
          <p className="text-xs text-gray-400 mt-4 text-center">
            Varsayılan şifre: <code className="bg-gray-100 dark:bg-gray-800 px-1 rounded">123456</code> (üretimde ADMIN_PASSWORD env ile değiştir)
          </p>
        </motion.div>
      </main>
    );
  }

  if (!settings) return <main className="p-8">Yükleniyor...</main>;

  return (
    <main className="min-h-screen bg-gradient-to-b from-gray-50 to-gray-100 dark:from-gray-950 dark:to-gray-900 text-gray-900 dark:text-gray-100">
      <div className="max-w-6xl mx-auto p-4 md:p-6">
        <header className="flex items-center justify-between mb-4 flex-wrap gap-3">
          <div className="flex items-center gap-3">
            <Link href="/" className="text-sm text-gray-500 hover:text-gray-900 dark:hover:text-white">← Anasayfa</Link>
            <h1 className="text-2xl font-bold bg-gradient-to-r from-orange-500 to-red-500 bg-clip-text text-transparent">
              Admin Paneli
            </h1>
          </div>
          <button
            onClick={handleLogout}
            className="px-3 py-1.5 text-sm rounded-lg bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 hover:border-rose-400"
          >
            Çıkış
          </button>
        </header>

        <GlobalStatusBar onNavigate={(tab) => setActiveTab(tab as Tab)} />

        <div className="flex flex-col md:flex-row gap-6">
          <nav className="md:w-56 shrink-0">
            <div className="flex md:flex-col gap-1 overflow-x-auto md:overflow-visible bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-100 dark:border-gray-800 p-2">
              {TABS.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`relative flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition whitespace-nowrap ${
                    activeTab === tab.id
                      ? "text-white"
                      : "text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800"
                  }`}
                >
                  {activeTab === tab.id && (
                    <motion.span
                      layoutId="admin-tab"
                      className="absolute inset-0 bg-gradient-to-r from-blue-500 to-blue-600 rounded-lg"
                      transition={{ type: "spring", stiffness: 500, damping: 35 }}
                    />
                  )}
                  <span className="relative z-10">{tab.icon}</span>
                  <span className="relative z-10">{tab.label}</span>
                </button>
              ))}
            </div>
          </nav>

          <div className="flex-1 min-w-0">
            <AnimatePresence mode="wait">
              <motion.div
                key={activeTab}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ duration: 0.2 }}
                className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-100 dark:border-gray-800 p-5"
              >
                {activeTab === "dashboard" && <DashboardTab />}
                {activeTab === "stores" && <StoresTab settings={settings} onSave={(payload) => updateSection("stores", payload)} busy={busy} />}
                {activeTab === "scheduler" && <SchedulerTab settings={settings} onSave={(payload) => updateSection("scheduler", payload)} busy={busy} />}
                {activeTab === "health" && <HealthTab />}
                {activeTab === "webhooks" && <WebhookTab settings={settings} onSave={(payload) => updateSection("webhooks", payload)} busy={busy} />}
                {activeTab === "backup" && <BackupTab />}
                {activeTab === "theme" && <ThemeTab settings={settings} onSave={(payload) => updateSection("theme", payload)} busy={busy} />}
                {activeTab === "social" && <SocialTab settings={settings} onSave={(payload) => updateSection("social", payload)} busy={busy} />}
                {activeTab === "auto_share" && <AutoShareTab settings={settings} onSave={(payload) => updateSection("auto_share", payload)} busy={busy} />}
                {activeTab === "boycott" && <BoycottTab />}
                {activeTab === "maintenance" && <MaintenanceTab settings={settings} onSave={(payload) => updateSection("maintenance", payload)} busy={busy} />}
                {activeTab === "logs" && <LogsTab />}
                {activeTab === "docs" && <DocsTab />}
              </motion.div>
            </AnimatePresence>
          </div>
        </div>
      </div>
    </main>
  );
}

type TabProps = { settings: Settings; onSave: (payload: Record<string, unknown>) => Promise<boolean>; busy: boolean };

type ScrapeStatus = "idle" | "running" | "completed" | "error" | "disabled";
interface PlatformStatus { status: ScrapeStatus; message: string; current_category: string | null; updated_at: string | null }

function DashboardTab() {
  const [stats, setStats] = useState<{
    total: number;
    by_platform: Record<string, number>;
    by_category: Record<string, number>;
    avg_discount: number;
    high_discount_count: number;
    top_deals: Array<{ title: string; platform: string; discount: number; price: string; link: string }>;
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [scrapeStatuses, setScrapeStatuses] = useState<Record<string, PlatformStatus>>({});
  const [globalStatus, setGlobalStatus] = useState<{ status: string; message: string; updated_at: string } | null>(null);
  const [startingAll, setStartingAll] = useState(false);

  // Stats — bir defa
  useEffect(() => {
    (async () => {
      try {
        const pw = typeof window !== "undefined" ? localStorage.getItem("multiscout_admin_pw") : null;
        if (!pw) return;
        const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
        const res = await fetch(`${API}/api/admin/stats`, { headers: { "X-ADMIN-PASSWORD": pw } });
        if (res.ok) {
          const data = await res.json();
          setStats(data.data);
        }
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  // Scrape status — her 5 saniyede bir poll (tarama varsa)
  useEffect(() => {
    const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    let stopped = false;
    const fetchStatus = async () => {
      try {
        const res = await fetch(`${API}/api/scrape-all-status`);
        if (!res.ok) return;
        const json = await res.json();
        if (stopped) return;
        const d = json.data || {};
        const { status, message, updated_at, ...platforms } = d;
        setGlobalStatus({ status: status || "idle", message: message || "", updated_at: updated_at || "" });
        setScrapeStatuses(platforms as Record<string, PlatformStatus>);
      } catch {}
    };
    fetchStatus();
    const interval = setInterval(fetchStatus, 5000);
    return () => { stopped = true; clearInterval(interval); };
  }, []);

  const scrapeAll = async () => {
    if (startingAll) return;
    if (!confirm("Tüm aktif platformlar için tarama başlatılsın mı? Bu işlem uzun sürebilir.")) return;
    setStartingAll(true);
    try {
      const pw = localStorage.getItem("multiscout_admin_pw");
      const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${API}/api/scrape-all?platform=all`, {
        method: "POST",
        headers: { "X-ADMIN-PASSWORD": pw || "" },
      });
      if (res.ok) toast.success("Tüm platformların taraması başlatıldı");
      else if (res.status === 409) toast.warning("Bir tarama zaten çalışıyor");
      else toast.error("Tarama başlatılamadı");
    } finally {
      setStartingAll(false);
    }
  };

  // Running platform sayısı
  const runningPlatforms = Object.entries(scrapeStatuses).filter(([, v]) => v?.status === "running");
  const erroredPlatforms = Object.entries(scrapeStatuses).filter(([, v]) => v?.status === "error");
  const isGlobalRunning = globalStatus?.status === "running" || runningPlatforms.length > 0;

  if (loading) return <div className="text-gray-500">Yükleniyor...</div>;
  if (!stats) return <div className="text-gray-500">İstatistik alınamadı.</div>;

  const totalPlatforms = Object.keys(stats.by_platform).length;
  const maxPlatformCount = Math.max(...Object.values(stats.by_platform), 1);
  const maxCategoryCount = Math.max(...Object.values(stats.by_category), 1);

  return (
    <div className="space-y-6">
      {/* Canlı tarama durumu */}
      <section className={`rounded-xl border p-4 ${
        isGlobalRunning
          ? "bg-blue-50 dark:bg-blue-900/20 border-blue-300 dark:border-blue-700/50"
          : erroredPlatforms.length > 0
          ? "bg-rose-50 dark:bg-rose-900/20 border-rose-300 dark:border-rose-700/50"
          : "bg-gray-50 dark:bg-gray-800/50 border-gray-200 dark:border-gray-700"
      }`}>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className={`w-3 h-3 rounded-full ${
              isGlobalRunning ? "bg-blue-500 animate-pulse" : erroredPlatforms.length > 0 ? "bg-rose-500" : "bg-green-500"
            }`} />
            <div>
              <div className="font-bold text-sm">
                {isGlobalRunning ? `${runningPlatforms.length} platform taranıyor` : erroredPlatforms.length > 0 ? `${erroredPlatforms.length} platformda hata` : "Tarama yapılmıyor"}
              </div>
              {globalStatus?.updated_at && (
                <div className="text-xs text-gray-500 dark:text-gray-400">
                  Son güncelleme: {new Date(globalStatus.updated_at).toLocaleString("tr-TR")}
                </div>
              )}
            </div>
          </div>
          <button
            onClick={scrapeAll}
            disabled={startingAll || isGlobalRunning}
            className="px-4 py-2 rounded-lg bg-gradient-to-r from-blue-500 to-blue-600 text-white text-sm font-bold shadow-sm hover:shadow-md disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {startingAll ? "Başlatılıyor..." : isGlobalRunning ? "Çalışıyor..." : "🚀 Hepsini Tara"}
          </button>
        </div>
        {runningPlatforms.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1.5">
            {runningPlatforms.slice(0, 12).map(([p]) => (
              <span key={p} className="text-[10px] px-2 py-0.5 rounded-full bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300 font-medium">
                {STORE_LABELS[p] || p}
              </span>
            ))}
            {runningPlatforms.length > 12 && (
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 font-medium">
                +{runningPlatforms.length - 12}
              </span>
            )}
          </div>
        )}
      </section>

      <h2 className="text-lg font-bold">İstatistikler</h2>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Stat label="Toplam Fırsat" value={stats.total} accent="from-blue-500 to-blue-600" />
        <Stat label="Platform" value={totalPlatforms} accent="from-purple-500 to-purple-600" />
        <Stat label="Ortalama İndirim" value={`%${stats.avg_discount}`} accent="from-orange-500 to-red-500" />
        <Stat label="%50+ Fırsat" value={stats.high_discount_count} accent="from-rose-500 to-pink-600" />
      </div>

      <section>
        <div className="flex items-baseline justify-between mb-2">
          <h3 className="text-sm font-bold">Platform Dağılımı</h3>
          <span className="text-[10px] text-gray-500 dark:text-gray-400">
            <span className="inline-block w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse mr-1" />tarıyor
            <span className="inline-block w-1.5 h-1.5 rounded-full bg-green-500 ml-2 mr-1" />tamamlandı
            <span className="inline-block w-1.5 h-1.5 rounded-full bg-rose-500 ml-2 mr-1" />hata
            <span className="inline-block w-1.5 h-1.5 rounded-full bg-gray-400 ml-2 mr-1" />beklemede
          </span>
        </div>
        <div className="space-y-1.5">
          {Object.entries(stats.by_platform).sort((a, b) => b[1] - a[1]).map(([p, c]) => {
            const ps = scrapeStatuses[p];
            const statusColor = ps?.status === "running" ? "bg-blue-500 animate-pulse"
              : ps?.status === "completed" ? "bg-green-500"
              : ps?.status === "error" ? "bg-rose-500"
              : ps?.status === "disabled" ? "bg-gray-300" : "bg-gray-400";
            const lastUpdate = ps?.updated_at ? new Date(ps.updated_at).toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" }) : "";
            return (
              <div key={p} className="flex items-center gap-2" title={ps?.message || ""}>
                <span className={`w-2 h-2 rounded-full shrink-0 ${statusColor}`} />
                <span className="w-24 text-xs text-gray-600 dark:text-gray-400 truncate">{STORE_LABELS[p] || p}</span>
                <div className="flex-1 h-5 bg-gray-100 dark:bg-gray-800 rounded overflow-hidden">
                  <motion.div initial={{ width: 0 }} animate={{ width: `${(c / maxPlatformCount) * 100}%` }} transition={{ duration: 0.6 }} className="h-full bg-gradient-to-r from-blue-500 to-blue-600 rounded" />
                </div>
                <span className="w-10 text-right text-[10px] text-gray-400 hidden sm:inline">{lastUpdate}</span>
                <span className="w-12 text-right text-xs font-mono">{c}</span>
              </div>
            );
          })}
        </div>
      </section>

      <section>
        <h3 className="text-sm font-bold mb-2">Top Kategoriler</h3>
        <div className="space-y-1.5">
          {Object.entries(stats.by_category).map(([c, n]) => (
            <div key={c} className="flex items-center gap-2">
              <span className="w-32 text-xs text-gray-600 dark:text-gray-400 truncate">{c}</span>
              <div className="flex-1 h-4 bg-gray-100 dark:bg-gray-800 rounded overflow-hidden">
                <motion.div initial={{ width: 0 }} animate={{ width: `${(n / maxCategoryCount) * 100}%` }} transition={{ duration: 0.6 }} className="h-full bg-gradient-to-r from-orange-400 to-red-500" />
              </div>
              <span className="w-10 text-right text-xs font-mono">{n}</span>
            </div>
          ))}
        </div>
      </section>

      <section>
        <h3 className="text-sm font-bold mb-2">Top 10 İndirim</h3>
        <div className="space-y-1">
          {stats.top_deals.map((d, i) => (
            <a key={i} href={d.link} target="_blank" rel="noreferrer" className="flex items-center gap-3 px-3 py-2 bg-gray-50 dark:bg-gray-800/50 rounded hover:bg-gray-100 dark:hover:bg-gray-800 transition">
              <span className="font-bold text-rose-500 w-12">%{d.discount}</span>
              <span className="flex-1 text-sm truncate">{d.title}</span>
              <span className="text-xs text-gray-500 hidden sm:inline">{d.platform}</span>
              <span className="text-sm font-bold">{d.price}</span>
            </a>
          ))}
        </div>
      </section>
    </div>
  );
}

function Stat({ label, value, accent }: { label: string; value: string | number; accent: string }) {
  return (
    <div className={`bg-gradient-to-br ${accent} rounded-xl p-3 text-white shadow-sm`}>
      <div className="text-xs opacity-80">{label}</div>
      <div className="text-2xl font-bold mt-1">{value}</div>
    </div>
  );
}

interface BoycottCategory { label: string; parent: string; brands: string[] }
interface BoycottRaw { version: string; source: string; categories: Record<string, BoycottCategory>; excluded_keywords: string[] }

function BoycottTab() {
  const [data, setData] = useState<BoycottRaw | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeCat, setActiveCat] = useState<string>("");
  const [newBrand, setNewBrand] = useState("");
  const [excludedText, setExcludedText] = useState("");
  const [refreshing, setRefreshing] = useState(false);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const pw = typeof window !== "undefined" ? localStorage.getItem("multiscout_admin_pw") : null;
      if (!pw) {
        setError("Admin oturumu bulunamadı. Sayfayı yenileyip tekrar giriş yap.");
        return;
      }
      const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      let res: Response;
      try {
        res = await fetch(`${API}/api/admin/boycott-raw`, { headers: { "X-ADMIN-PASSWORD": pw } });
      } catch (netErr) {
        setError(`Backend'e ulaşılamadı (${API}). Sebep: ${(netErr as Error).message}`);
        return;
      }
      if (res.status === 401) {
        setError("Şifre reddedildi (401). Çıkış yapıp yeniden giriş yap.");
        return;
      }
      if (!res.ok) {
        const body = await res.text().catch(() => "");
        setError(`Backend hata döndü: HTTP ${res.status}. ${body.slice(0, 200)}`);
        return;
      }
      let r: { status?: string; data?: BoycottRaw };
      try {
        r = await res.json();
      } catch {
        setError("Cevap JSON olarak ayrıştırılamadı.");
        return;
      }
      if (!r.data || typeof r.data !== "object" || !r.data.categories) {
        setError("Cevap geldi ama beklenen veri formatında değil (categories eksik).");
        return;
      }
      setData(r.data);
      const keys = Object.keys(r.data.categories);
      if (keys.length) setActiveCat(keys[0]);
      setExcludedText((r.data.excluded_keywords || []).join("\n"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const refetchFromSource = async () => {
    setRefreshing(true);
    try {
      const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const r = await fetch(`${API}/api/boycott-brands?refresh=true`);
      if (r.ok) {
        toast.success("Kaynaktan yenilendi");
        await load();
      } else {
        toast.error(`Kaynak yenilenemedi (HTTP ${r.status})`);
      }
    } catch (e) {
      toast.error(`Yenileme hatası: ${(e as Error).message}`);
    } finally {
      setRefreshing(false);
    }
  };

  const save = async () => {
    if (!data) return;
    setSaving(true);
    const payload = { ...data, excluded_keywords: excludedText.split("\n").map((s) => s.trim()).filter(Boolean) };
    const pw = localStorage.getItem("multiscout_admin_pw");
    const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    try {
      const res = await fetch(`${API}/api/admin/boycott-raw`, { method: "PUT", headers: { "Content-Type": "application/json", "X-ADMIN-PASSWORD": pw || "" }, body: JSON.stringify(payload) });
      if (res.ok) toast.success("Boykot listesi kaydedildi");
      else if (res.status === 401) toast.error("Şifre reddedildi (401)");
      else toast.error(`Kaydedilemedi: HTTP ${res.status}`);
    } catch (e) {
      toast.error(`Network hatası: ${(e as Error).message}`);
    } finally {
      setSaving(false);
    }
  };

  const addBrand = () => {
    if (!data || !activeCat || !newBrand.trim()) return;
    const cleaned = newBrand.trim().toLowerCase();
    if (data.categories[activeCat].brands.includes(cleaned)) {
      toast.error("Zaten ekli");
      return;
    }
    const next = { ...data, categories: { ...data.categories, [activeCat]: { ...data.categories[activeCat], brands: [...data.categories[activeCat].brands, cleaned] } } };
    setData(next);
    setNewBrand("");
  };

  const removeBrand = (brand: string) => {
    if (!data) return;
    const next = { ...data, categories: { ...data.categories, [activeCat]: { ...data.categories[activeCat], brands: data.categories[activeCat].brands.filter((b) => b !== brand) } } };
    setData(next);
  };

  if (loading) {
    return (
      <div className="space-y-3">
        <div className="h-6 w-48 bg-gray-100 dark:bg-gray-800 rounded animate-pulse" />
        <div className="h-4 w-72 bg-gray-100 dark:bg-gray-800 rounded animate-pulse" />
        <div className="flex gap-2 flex-wrap mt-3">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="h-7 w-24 bg-gray-100 dark:bg-gray-800 rounded-full animate-pulse" />
          ))}
        </div>
      </div>
    );
  }
  if (error || !data) {
    return (
      <div className="rounded-lg border border-rose-200 dark:border-rose-900/50 bg-rose-50 dark:bg-rose-950/30 p-4">
        <div className="flex items-start gap-3">
          <span className="text-xl">⚠️</span>
          <div className="flex-1 min-w-0">
            <p className="font-semibold text-rose-700 dark:text-rose-300">Boykot listesi yüklenemedi</p>
            <p className="text-sm text-rose-600 dark:text-rose-400 mt-1 break-words">{error || "Bilinmeyen hata."}</p>
            <div className="flex gap-2 mt-3">
              <button onClick={load} className="px-3 py-1.5 rounded-lg bg-rose-500 text-white text-sm font-medium hover:bg-rose-600">
                ↻ Yeniden Dene
              </button>
              <button onClick={refetchFromSource} disabled={refreshing} className="px-3 py-1.5 rounded-lg bg-white dark:bg-gray-900 border border-rose-200 dark:border-rose-900/50 text-sm">
                {refreshing ? "Kaynaktan çekiliyor..." : "Kaynaktan Yenile"}
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  const totalBrands = Object.values(data.categories).reduce((s, c) => s + c.brands.length, 0);

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between flex-wrap gap-2">
        <div>
          <h2 className="text-lg font-bold">Boykot Listesi</h2>
          <p className="text-sm text-gray-500 dark:text-gray-400">Toplam {totalBrands} marka, {Object.keys(data.categories).length} kategori. Sürüm: {data.version}.</p>
        </div>
        <div className="flex gap-2">
          <button onClick={refetchFromSource} disabled={refreshing} className="px-3 py-2 rounded-lg bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 text-sm font-medium disabled:opacity-50">
            {refreshing ? "Yenileniyor..." : "↻ Kaynaktan Yenile"}
          </button>
          <button onClick={save} disabled={saving} className="px-4 py-2 rounded-lg bg-blue-500 text-white font-semibold disabled:opacity-50">{saving ? "Kaydediliyor..." : "Tümünü Kaydet"}</button>
        </div>
      </div>

      <div className="flex gap-2 flex-wrap">
        {Object.entries(data.categories).map(([k, v]) => (
          <button key={k} onClick={() => setActiveCat(k)} className={`px-3 py-1.5 rounded-full text-xs font-medium ${activeCat === k ? "bg-rose-500 text-white" : "bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-gray-700"}`}>
            {v.label} ({v.brands.length})
          </button>
        ))}
      </div>

      {activeCat && data.categories[activeCat] && (
        <div className="bg-gray-50 dark:bg-gray-800/50 rounded-lg p-3">
          <div className="text-xs text-gray-500 mb-2">Ana şirket: {data.categories[activeCat].parent}</div>
          <div className="flex gap-1.5 flex-wrap mb-3">
            {data.categories[activeCat].brands.map((b) => (
              <span key={b} className="inline-flex items-center gap-1 px-2 py-1 rounded-full bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 text-xs">
                {b}
                <button onClick={() => removeBrand(b)} className="text-rose-500 hover:text-rose-700">×</button>
              </span>
            ))}
          </div>
          <div className="flex gap-2">
            <input value={newBrand} onChange={(e) => setNewBrand(e.target.value)} onKeyDown={(e) => e.key === "Enter" && addBrand()} placeholder="yeni marka adı" className="flex-1 px-3 py-1.5 rounded-lg bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 text-sm" />
            <button onClick={addBrand} className="px-3 py-1.5 rounded-lg bg-green-500 text-white text-sm font-medium">+ Ekle</button>
          </div>
        </div>
      )}

      <div>
        <h3 className="text-sm font-semibold mb-2">İstisna Anahtarlar (false positive'leri eler)</h3>
        <p className="text-xs text-gray-500 mb-2">Her satıra bir kelime. Örnek: <code>axess</code>, <code>kotonlu</code>, <code>kokoreç</code></p>
        <textarea value={excludedText} onChange={(e) => setExcludedText(e.target.value)} rows={5} className="w-full px-3 py-2 rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 font-mono text-sm" />
      </div>
    </div>
  );
}

function StoresTab({ settings, onSave, busy }: TabProps) {
  const [stores, setStores] = useState(settings.stores);
  const [query, setQuery] = useState("");
  const [productCounts, setProductCounts] = useState<Record<string, number>>({});
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});
  const [scrapingFor, setScrapingFor] = useState<string | null>(null);

  // Stats endpoint'ten her platform için ürün sayısını al
  useEffect(() => {
    (async () => {
      try {
        const pw = typeof window !== "undefined" ? localStorage.getItem("multiscout_admin_pw") : null;
        if (!pw) return;
        const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
        const res = await fetch(`${API}/api/admin/stats`, { headers: { "X-ADMIN-PASSWORD": pw } });
        if (res.ok) {
          const data = await res.json();
          setProductCounts(data.data?.by_platform || {});
        }
      } catch {}
    })();
  }, []);

  const toggle = (k: string) => setStores({ ...stores, [k]: !stores[k] });
  const setAll = (val: boolean) => setStores(Object.fromEntries(Object.keys(stores).map(k => [k, val])));
  const setCategory = (catId: string, val: boolean) => {
    const cat = STORE_CATEGORIES.find(c => c.id === catId);
    if (!cat) return;
    setStores({ ...stores, ...Object.fromEntries(cat.stores.filter(s => s in stores).map(s => [s, val])) });
  };
  const save = () => onSave(stores);
  const enabledCount = Object.values(stores).filter(Boolean).length;
  const totalCount = Object.keys(stores).length;

  const scrapeNow = async (platform: string) => {
    setScrapingFor(platform);
    try {
      const pw = localStorage.getItem("multiscout_admin_pw");
      const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${API}/api/scrape-all?platform=${platform}`, {
        method: "POST",
        headers: { "X-ADMIN-PASSWORD": pw || "" },
      });
      if (res.ok) toast.success(`${STORE_LABELS[platform] || platform} taraması başlatıldı`);
      else if (res.status === 409) toast.warning("Bir tarama zaten çalışıyor");
      else toast.error("Tarama başlatılamadı");
    } finally {
      setScrapingFor(null);
    }
  };

  // Filter stores by query
  const q = query.trim().toLowerCase();
  const filteredKeys = Object.keys(stores).filter(k => {
    if (!q) return true;
    const label = (STORE_LABELS[k] || k).toLowerCase();
    return label.includes(q) || k.toLowerCase().includes(q);
  });

  // Group stores by category
  const grouped: Record<string, string[]> = {};
  STORE_CATEGORIES.forEach(c => { grouped[c.id] = []; });
  grouped.other = [];
  filteredKeys.forEach(k => {
    const catId = getStoreCategory(k);
    if (!(catId in grouped)) grouped[catId] = [];
    grouped[catId].push(k);
  });
  const visibleCategories = [...STORE_CATEGORIES, { id: "other", label: "Diğer", icon: "📦", stores: [] }]
    .filter(c => grouped[c.id]?.length > 0);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold">Mağaza Açık / Kapalı</h2>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            {enabledCount}/{totalCount} aktif. Kapalı mağazalar kullanıcılara görünmez ve otomatik taramaya alınmaz.
          </p>
        </div>
        <div className="flex gap-2 flex-wrap">
          <button onClick={() => setAll(true)} className="px-3 py-1.5 rounded-lg bg-green-500 text-white text-xs font-medium hover:bg-green-600">Hepsini Aç</button>
          <button onClick={() => setAll(false)} className="px-3 py-1.5 rounded-lg bg-gray-500 text-white text-xs font-medium hover:bg-gray-600">Hepsini Kapat</button>
          <button onClick={save} disabled={busy} className="px-4 py-1.5 rounded-lg bg-blue-500 text-white text-sm font-semibold disabled:opacity-50">
            {busy ? "Kaydediliyor..." : "Kaydet"}
          </button>
        </div>
      </div>

      {/* Search bar */}
      <div className="relative">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Mağaza ara… (örn: koton, market, watsons)"
          className="w-full pl-9 pr-3 py-2 rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400">🔍</span>
        {query && (
          <button onClick={() => setQuery("")} className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600">×</button>
        )}
      </div>

      {/* Category groups */}
      <div className="space-y-3">
        {visibleCategories.map((cat) => {
          const catStores = grouped[cat.id];
          const catEnabled = catStores.filter(k => stores[k]).length;
          const isCollapsed = collapsed[cat.id] === true;
          return (
            <div key={cat.id} className="border border-gray-200 dark:border-gray-800 rounded-xl overflow-hidden">
              <div className="flex items-center justify-between px-3 py-2 bg-gray-50 dark:bg-gray-800/50">
                <button
                  onClick={() => setCollapsed({ ...collapsed, [cat.id]: !isCollapsed })}
                  className="flex items-center gap-2 text-sm font-semibold flex-1 text-left"
                >
                  <span>{isCollapsed ? "▶" : "▼"}</span>
                  <span>{cat.icon}</span>
                  <span>{cat.label}</span>
                  <span className="text-xs text-gray-500 font-normal">({catEnabled}/{catStores.length})</span>
                </button>
                <div className="flex gap-1">
                  <button onClick={() => setCategory(cat.id, true)} className="px-2 py-0.5 rounded text-[10px] bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300 hover:bg-green-200">Aç</button>
                  <button onClick={() => setCategory(cat.id, false)} className="px-2 py-0.5 rounded text-[10px] bg-gray-200 text-gray-700 dark:bg-gray-700 dark:text-gray-300 hover:bg-gray-300">Kapat</button>
                </div>
              </div>
              {!isCollapsed && (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 p-2">
                  {catStores.map((k) => {
                    const v = stores[k];
                    const cnt = productCounts[k];
                    const isScraping = scrapingFor === k;
                    return (
                      <div key={k} className={`flex items-center gap-2 px-3 py-2 rounded-lg border transition ${
                        v ? "bg-green-50/50 dark:bg-green-900/10 border-green-200 dark:border-green-700/30" : "bg-gray-50 dark:bg-gray-800 border-gray-200 dark:border-gray-700"
                      }`}>
                        <label className="flex items-center gap-2 flex-1 cursor-pointer min-w-0">
                          <input type="checkbox" checked={v} onChange={() => toggle(k)} className="w-4 h-4 accent-green-600 shrink-0" />
                          <span className="text-sm font-medium truncate">{STORE_LABELS[k] || k}</span>
                          {cnt !== undefined && cnt > 0 && (
                            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300 font-mono shrink-0">
                              {cnt}
                            </span>
                          )}
                        </label>
                        <button
                          onClick={() => scrapeNow(k)}
                          disabled={isScraping || !v}
                          title={!v ? "Önce mağazayı aç" : isScraping ? "Tarama başlatılıyor..." : "Şimdi tara"}
                          className="text-[10px] px-2 py-1 rounded-full bg-blue-500 text-white hover:bg-blue-600 disabled:bg-gray-300 dark:disabled:bg-gray-600 disabled:cursor-not-allowed shrink-0"
                        >
                          {isScraping ? "..." : "Tara"}
                        </button>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
        {visibleCategories.length === 0 && (
          <div className="text-center text-sm text-gray-500 dark:text-gray-400 py-8">
            "{query}" için sonuç bulunamadı.
          </div>
        )}
      </div>
    </div>
  );
}

const TIER_META: Record<string, { label: string; icon: string; hint: string }> = {
  market: { label: "Market (Gıda)", icon: "🛒", hint: "A101/BİM/ŞOK — taze fiyat takibi" },
  fashion: { label: "Moda", icon: "👗", hint: "LCW/Koton/Mavi vb." },
  marketplace: { label: "Marketplace", icon: "🛍️", hint: "Trendyol/Amazon/N11/Hepsiburada" },
  electronics: { label: "Elektronik & Tech", icon: "💻", hint: "Beko/Arçelik/Vestel/Apple/Huawei" },
  home: { label: "Ev / Dekorasyon", icon: "🏠", hint: "Karaca/Vivense/Tepe Home vs." },
  default: { label: "Diğer (Default)", icon: "📦", hint: "Yukarıda kapsanmayan tüm aktif platformlar" },
};

function SchedulerTab({ settings, onSave, busy }: TabProps) {
  const [s, setS] = useState<SchedulerSettings>(settings.scheduler);
  const [restarting, setRestarting] = useState(false);

  const toggleTier = (tier: string, enabled: boolean) => {
    setS({ ...s, tiers: { ...s.tiers, [tier]: { ...s.tiers[tier], enabled } } });
  };
  const setTierField = (tier: string, field: keyof SchedulerTier, val: number) => {
    setS({ ...s, tiers: { ...s.tiers, [tier]: { ...s.tiers[tier], [field]: val } } });
  };

  const save = async () => {
    const ok = await onSave(s as unknown as Record<string, unknown>);
    if (ok) toast.success("Ayarlar kaydedildi. Etkin olması için scheduler'ı yeniden başlat.");
  };

  const restart = async () => {
    if (!confirm("Scheduler yeniden başlatılsın mı? Yeni tier ayarları uygulanır.")) return;
    setRestarting(true);
    try {
      const pw = localStorage.getItem("multiscout_admin_pw");
      const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${API}/api/admin/scheduler/restart`, {
        method: "POST",
        headers: { "X-ADMIN-PASSWORD": pw || "" },
      });
      if (res.ok) toast.success("Scheduler yeniden başlatıldı");
      else toast.error("Yeniden başlatma hatası");
    } finally {
      setRestarting(false);
    }
  };

  const tiers = s.tiers || {};
  const tierKeys = Object.keys(tiers);

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <h2 className="text-lg font-bold">Çok-katmanlı Tarama Ayarları</h2>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Her tier kendi interval ve min-indirim eşiğine sahip. Tier'larda olmayan platformlar "Diğer (Default)" tier'ına düşer.
          </p>
        </div>
        <div className="flex gap-2 flex-wrap">
          <button onClick={save} disabled={busy} className="px-4 py-1.5 rounded-lg bg-blue-500 text-white text-sm font-semibold disabled:opacity-50">
            {busy ? "Kaydediliyor..." : "Kaydet"}
          </button>
          <button onClick={restart} disabled={restarting} className="px-4 py-1.5 rounded-lg bg-purple-500 text-white text-sm font-semibold disabled:opacity-50">
            {restarting ? "Yeniden başlatılıyor..." : "🔄 Scheduler'ı yeniden başlat"}
          </button>
        </div>
      </div>

      <label className="flex items-center gap-3 p-3 rounded-lg bg-gray-50 dark:bg-gray-800/50 border border-gray-200 dark:border-gray-700">
        <input type="checkbox" checked={s.enabled} onChange={(e) => setS({ ...s, enabled: e.target.checked })} className="w-5 h-5 accent-blue-600" />
        <div>
          <div className="font-semibold text-sm">Scheduler genel anahtarı</div>
          <div className="text-xs text-gray-500 dark:text-gray-400">Kapalıysa hiçbir tier çalışmaz (tier'lar zaten kapalıyken bypass etmez).</div>
        </div>
      </label>

      <div className="space-y-3">
        {tierKeys.map((tk) => {
          const t = tiers[tk];
          const meta = TIER_META[tk] || { label: tk, icon: "⚙️", hint: "" };
          const platformList = (t.platforms || []).map(p => STORE_LABELS[p] || p);
          return (
            <div key={tk} className={`rounded-xl border p-4 transition ${
              t.enabled ? "bg-white dark:bg-gray-900 border-blue-200 dark:border-blue-700/40" : "bg-gray-50 dark:bg-gray-800/30 border-gray-200 dark:border-gray-700 opacity-70"
            }`}>
              <div className="flex items-center justify-between gap-3 flex-wrap mb-3">
                <div className="flex items-center gap-2">
                  <span className="text-2xl">{meta.icon}</span>
                  <div>
                    <div className="font-bold">{meta.label}</div>
                    <div className="text-xs text-gray-500 dark:text-gray-400">{meta.hint}</div>
                  </div>
                </div>
                <label className="flex items-center gap-2 text-sm">
                  <input type="checkbox" checked={t.enabled} onChange={(e) => toggleTier(tk, e.target.checked)} className="w-4 h-4 accent-blue-600" />
                  <span>Aktif</span>
                </label>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <label className="block">
                  <span className="text-xs text-gray-600 dark:text-gray-400">Tarama aralığı (dakika)</span>
                  <input type="number" min="5" value={t.interval_min}
                    onChange={(e) => setTierField(tk, "interval_min", parseInt(e.target.value) || 60)}
                    className="mt-1 w-full px-3 py-2 rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 text-sm" />
                </label>
                <label className="block">
                  <span className="text-xs text-gray-600 dark:text-gray-400">Minimum indirim (%)</span>
                  <input type="number" min="0" max="90" value={t.min_discount}
                    onChange={(e) => setTierField(tk, "min_discount", parseInt(e.target.value) || 0)}
                    className="mt-1 w-full px-3 py-2 rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 text-sm" />
                </label>
              </div>
              {platformList.length > 0 && (
                <div className="mt-3">
                  <div className="text-xs text-gray-500 mb-1">Kapsanan platformlar ({platformList.length})</div>
                  <div className="flex flex-wrap gap-1">
                    {platformList.slice(0, 16).map((p) => (
                      <span key={p} className="text-[10px] px-2 py-0.5 rounded-full bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300">{p}</span>
                    ))}
                    {platformList.length > 16 && <span className="text-[10px] text-gray-500">+{platformList.length - 16}</span>}
                  </div>
                </div>
              )}
              {tk === "default" && (
                <div className="text-xs text-gray-500 mt-2 italic">
                  Diğer tier'larda kapsanmayan aktif platformlar otomatik buraya düşer.
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function HealthTab() {
  const [data, setData] = useState<{
    status: string;
    uptime_sec: number;
    now: string;
    checks: Record<string, Record<string, unknown>>;
  } | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchHealth = async () => {
    try {
      const pw = typeof window !== "undefined" ? localStorage.getItem("multiscout_admin_pw") : null;
      if (!pw) return;
      const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${API}/api/admin/health`, { headers: { "X-ADMIN-PASSWORD": pw } });
      if (res.ok) {
        const json = await res.json();
        setData(json.data);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHealth();
    const interval = setInterval(fetchHealth, 10000);
    return () => clearInterval(interval);
  }, []);

  if (loading) return <div className="text-gray-500">Yükleniyor...</div>;
  if (!data) return <div className="text-gray-500">Health alınamadı.</div>;

  const uptime = (() => {
    let s = data.uptime_sec;
    const d = Math.floor(s / 86400); s %= 86400;
    const h = Math.floor(s / 3600); s %= 3600;
    const m = Math.floor(s / 60);
    return [d && `${d}g`, h && `${h}sa`, m && `${m}dk`].filter(Boolean).join(" ") || "<1dk";
  })();

  const statusColor = data.status === "ok" ? "from-green-500 to-emerald-600"
    : data.status === "warning" ? "from-amber-500 to-orange-500"
    : "from-rose-500 to-red-600";

  const checks = data.checks || {};

  type CheckCard = { key: string; title: string; icon: string; ok: boolean | undefined; lines: string[] };
  const cards: CheckCard[] = [];

  const db = checks.db as { ok?: boolean; deal_count?: number; error?: string };
  cards.push({ key: "db", title: "Veritabanı", icon: "🗄️", ok: db?.ok, lines: db?.ok ? [`${db.deal_count ?? 0} deal`] : [db?.error || "Bağlanılamadı"] });

  const sched = checks.scheduler as { ok?: boolean; running?: boolean; jobs?: Array<{ id: string; next_run?: string }>; error?: string };
  cards.push({
    key: "scheduler",
    title: "Scheduler",
    icon: "⏰",
    ok: sched?.ok,
    lines: sched?.ok
      ? [`${sched.jobs?.length || 0} aktif job`, ...(sched.jobs?.slice(0, 3) || []).map(j => `${j.id} → ${j.next_run ? new Date(j.next_run).toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" }) : "?"}`)]
      : [sched?.error || "Çalışmıyor"],
  });

  const pw = checks.playwright as { ok?: boolean; version?: string; error?: string };
  cards.push({ key: "playwright", title: "Playwright", icon: "🎭", ok: pw?.ok, lines: pw?.ok ? [`v${pw.version}`] : [pw?.error || "Yok"] });

  const disk = checks.disk as { ok?: boolean; pct_free?: number; free_gb?: number; total_gb?: number; error?: string };
  cards.push({
    key: "disk",
    title: "Disk",
    icon: "💾",
    ok: disk?.ok,
    lines: disk?.ok ? [`%${disk.pct_free} boş`, `${disk.free_gb} / ${disk.total_gb} GB`] : [disk?.error || "Okunamadı"],
  });

  const mem = checks.memory as { ok?: boolean; pct_free?: number; free_mb?: number; total_mb?: number; error?: string };
  cards.push({
    key: "memory",
    title: "Bellek",
    icon: "🧠",
    ok: mem?.ok,
    lines: mem?.ok ? [`%${mem.pct_free} boş`, `${mem.free_mb} / ${mem.total_mb} MB`] : [mem?.error || "Okunamadı"],
  });

  cards.push({ key: "uptime", title: "Uptime", icon: "⏱️", ok: true, lines: [uptime] });

  return (
    <div className="space-y-5">
      <div className={`rounded-xl p-4 bg-gradient-to-r ${statusColor} text-white shadow-sm flex items-center justify-between flex-wrap gap-3`}>
        <div className="flex items-center gap-3">
          <span className="text-3xl">{data.status === "ok" ? "✅" : data.status === "warning" ? "⚠️" : "🚨"}</span>
          <div>
            <div className="text-sm opacity-80">Genel durum</div>
            <div className="text-2xl font-bold uppercase tracking-wide">{data.status}</div>
          </div>
        </div>
        <button onClick={fetchHealth} className="px-3 py-1.5 rounded-lg bg-white/20 hover:bg-white/30 text-white text-sm font-medium backdrop-blur-sm">
          🔄 Yenile
        </button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        {cards.map((c) => (
          <div key={c.key} className={`rounded-xl border p-3 ${
            c.ok ? "bg-green-50 dark:bg-green-900/15 border-green-200 dark:border-green-700/40"
            : c.ok === false ? "bg-rose-50 dark:bg-rose-900/15 border-rose-200 dark:border-rose-700/40"
            : "bg-gray-50 dark:bg-gray-800/50 border-gray-200 dark:border-gray-700"
          }`}>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-xl">{c.icon}</span>
              <span className="font-bold text-sm">{c.title}</span>
              <span className="ml-auto text-xs">{c.ok ? "✓" : c.ok === false ? "✗" : "·"}</span>
            </div>
            <div className="space-y-0.5">
              {c.lines.map((l, i) => (
                <div key={i} className="text-xs text-gray-700 dark:text-gray-300 truncate" title={l}>{l}</div>
              ))}
            </div>
          </div>
        ))}
      </div>

      <div className="text-xs text-gray-500 dark:text-gray-400">
        Otomatik yenileme: 10 saniye. Son güncelleme: {new Date(data.now).toLocaleString("tr-TR")}
      </div>
    </div>
  );
}

function WebhookTab({ settings, onSave, busy }: TabProps) {
  const [w, setW] = useState<Webhooks>(settings.webhooks);
  const [testingKind, setTestingKind] = useState<string | null>(null);

  const save = () => onSave(w as unknown as Record<string, unknown>);

  const sendTest = async (kind: "discord" | "slack") => {
    setTestingKind(kind);
    try {
      const pw = localStorage.getItem("multiscout_admin_pw");
      const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${API}/api/admin/test-webhook?kind=${kind}`, {
        method: "POST",
        headers: { "X-ADMIN-PASSWORD": pw || "" },
      });
      const json = await res.json();
      if (json.status === "success") toast.success(json.message || "Test gönderildi");
      else toast.error(json.message || "Gönderilemedi");
    } finally {
      setTestingKind(null);
    }
  };

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-bold">Discord / Slack Webhooks</h2>
        <p className="text-sm text-gray-500 dark:text-gray-400">
          Tarama sonrası eşik üstü deal'ler otomatik kanala gönderilir (son 1 saatte eklenenler, max 5 mesaj).
        </p>
      </div>

      <label className="flex items-center gap-3 p-3 rounded-lg bg-gray-50 dark:bg-gray-800/50 border border-gray-200 dark:border-gray-700">
        <input type="checkbox" checked={w.enabled} onChange={(e) => setW({ ...w, enabled: e.target.checked })} className="w-5 h-5 accent-blue-600" />
        <div>
          <div className="font-semibold text-sm">Webhook bildirimleri aktif</div>
          <div className="text-xs text-gray-500 dark:text-gray-400">Kapalıysa scheduler tarama sonrası kanala mesaj göndermez.</div>
        </div>
      </label>

      <label className="block">
        <span className="text-sm text-gray-600 dark:text-gray-400">Minimum indirim eşiği (%)</span>
        <input type="number" min="0" max="99" value={w.min_discount}
          onChange={(e) => setW({ ...w, min_discount: parseInt(e.target.value) || 50 })}
          className="mt-1 w-full px-3 py-2 rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 text-sm" />
        <span className="text-xs text-gray-400 mt-1 block">Bu yüzdenin üstündeki deal'ler webhook'a gider.</span>
      </label>

      <section className="rounded-xl border border-indigo-200 dark:border-indigo-700/40 bg-indigo-50/40 dark:bg-indigo-900/15 p-4">
        <div className="flex items-center justify-between gap-2 mb-2">
          <h3 className="font-bold flex items-center gap-2">💬 Discord</h3>
          <button onClick={() => sendTest("discord")} disabled={!w.discord_url || testingKind === "discord"}
            className="text-xs px-3 py-1 rounded bg-indigo-500 text-white font-medium disabled:opacity-50">
            {testingKind === "discord" ? "Gönderiliyor..." : "🚀 Test gönder"}
          </button>
        </div>
        <input type="text" value={w.discord_url} onChange={(e) => setW({ ...w, discord_url: e.target.value })}
          placeholder="https://discord.com/api/webhooks/123.../abcdef..."
          className="w-full px-3 py-2 rounded-lg bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 text-sm font-mono" />
        <div className="text-xs text-gray-500 dark:text-gray-400 mt-2">
          Discord kanal → ⚙️ Edit Channel → Integrations → Webhooks → New Webhook → Copy URL
        </div>
      </section>

      <section className="rounded-xl border border-emerald-200 dark:border-emerald-700/40 bg-emerald-50/40 dark:bg-emerald-900/15 p-4">
        <div className="flex items-center justify-between gap-2 mb-2">
          <h3 className="font-bold flex items-center gap-2">💼 Slack</h3>
          <button onClick={() => sendTest("slack")} disabled={!w.slack_url || testingKind === "slack"}
            className="text-xs px-3 py-1 rounded bg-emerald-500 text-white font-medium disabled:opacity-50">
            {testingKind === "slack" ? "Gönderiliyor..." : "🚀 Test gönder"}
          </button>
        </div>
        <input type="text" value={w.slack_url} onChange={(e) => setW({ ...w, slack_url: e.target.value })}
          placeholder="https://hooks.slack.com/services/T.../B.../..."
          className="w-full px-3 py-2 rounded-lg bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 text-sm font-mono" />
        <div className="text-xs text-gray-500 dark:text-gray-400 mt-2">
          Slack workspace → Apps → Incoming Webhooks → Add Configuration → Copy webhook URL
        </div>
      </section>

      <button onClick={save} disabled={busy} className="px-4 py-2 rounded-lg bg-blue-500 text-white font-semibold disabled:opacity-50">
        {busy ? "Kaydediliyor..." : "Kaydet"}
      </button>
    </div>
  );
}

function BackupTab() {
  const [busy, setBusy] = useState(false);
  const [opts, setOpts] = useState({ restoreSettings: true, restoreBoycott: true });
  const fileRef = useRef<HTMLInputElement | null>(null);

  const download = async () => {
    setBusy(true);
    try {
      const pw = localStorage.getItem("multiscout_admin_pw");
      const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${API}/api/admin/backup`, { headers: { "X-ADMIN-PASSWORD": pw || "" } });
      if (!res.ok) { toast.error("İndirilemedi"); return; }
      const blob = await res.blob();
      const cd = res.headers.get("Content-Disposition") || "";
      const m = cd.match(/filename="?([^";]+)/);
      const fname = m ? m[1] : `multiscout-backup-${new Date().toISOString().slice(0, 10)}.zip`;
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = fname;
      a.click();
      URL.revokeObjectURL(a.href);
      toast.success("Yedek indirildi");
    } finally {
      setBusy(false);
    }
  };

  const upload = async () => {
    const file = fileRef.current?.files?.[0];
    if (!file) { toast.warning("Önce bir .zip dosyası seç"); return; }
    if (!confirm(`'${file.name}' yedeği geri yüklensin mi? Mevcut config üzerine yazılacak.`)) return;
    setBusy(true);
    try {
      const pw = localStorage.getItem("multiscout_admin_pw");
      const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const form = new FormData();
      form.append("file", file);
      const url = `${API}/api/admin/restore?restore_settings=${opts.restoreSettings}&restore_boycott=${opts.restoreBoycott}`;
      const res = await fetch(url, {
        method: "POST",
        headers: { "X-ADMIN-PASSWORD": pw || "" },
        body: form,
      });
      const json = await res.json();
      if (json.status === "success") {
        toast.success(`Geri yüklendi: ${(json.restored || []).join(", ")}`);
        setTimeout(() => window.location.reload(), 1200);
      } else {
        toast.error(json.error || "Hata");
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-lg font-bold">Yedek Al / Geri Yükle</h2>
        <p className="text-sm text-gray-500 dark:text-gray-400">
          Admin ayarları (mağaza durumları, scheduler tier'ları, sosyal medya tokenları, webhook URL'leri, tema)
          ve boykot listesini ZIP olarak yedekler. <strong>Veritabanı (deal'ler) yedeklenmez</strong> — onu separately pg_dump ile alın.
        </p>
      </div>

      <section className="rounded-xl border border-blue-200 dark:border-blue-700/40 bg-blue-50/40 dark:bg-blue-900/15 p-4">
        <h3 className="font-bold flex items-center gap-2 mb-3">⬇️ Yedek Al</h3>
        <p className="text-xs text-gray-600 dark:text-gray-400 mb-3">
          ZIP içeriği: <code>admin_settings.json</code>, <code>boycott_brands.json</code>, <code>meta.json</code>
        </p>
        <button onClick={download} disabled={busy}
          className="px-4 py-2 rounded-lg bg-gradient-to-r from-blue-500 to-blue-600 text-white text-sm font-bold shadow-sm hover:shadow-md disabled:opacity-50">
          {busy ? "Hazırlanıyor..." : "📥 Yedek İndir (.zip)"}
        </button>
      </section>

      <section className="rounded-xl border border-amber-200 dark:border-amber-700/40 bg-amber-50/40 dark:bg-amber-900/15 p-4">
        <h3 className="font-bold flex items-center gap-2 mb-3">⬆️ Geri Yükle</h3>
        <p className="text-xs text-gray-600 dark:text-gray-400 mb-3">
          Yüklenen ZIP'ten config üzerine yazılır. Mevcut mağaza durumları, ayarlar vs. <strong>üzerine yazılır</strong>.
          İşlem sonrası sayfa yenilenir.
        </p>
        <input ref={fileRef} type="file" accept=".zip" className="block w-full text-sm text-gray-600 dark:text-gray-300 mb-3
          file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:bg-gray-200 dark:file:bg-gray-700 file:text-sm file:font-medium" />
        <div className="space-y-2 mb-3">
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={opts.restoreSettings} onChange={(e) => setOpts({ ...opts, restoreSettings: e.target.checked })} className="accent-blue-600" />
            <span>admin_settings.json'u geri yükle</span>
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={opts.restoreBoycott} onChange={(e) => setOpts({ ...opts, restoreBoycott: e.target.checked })} className="accent-blue-600" />
            <span>boycott_brands.json'u geri yükle</span>
          </label>
        </div>
        <button onClick={upload} disabled={busy}
          className="px-4 py-2 rounded-lg bg-gradient-to-r from-amber-500 to-orange-500 text-white text-sm font-bold shadow-sm hover:shadow-md disabled:opacity-50">
          {busy ? "Yükleniyor..." : "🔄 Geri Yükle"}
        </button>
      </section>
    </div>
  );
}

function ThemeTab({ settings, onSave, busy }: TabProps) {
  const [t, setT] = useState(settings.theme);
  return (
    <div className="space-y-4">
      <h2 className="text-lg font-bold">Tema & Marka</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <label className="block">
          <span className="text-sm text-gray-600 dark:text-gray-400">Logo / başlık metni</span>
          <input type="text" value={t.logo_text} onChange={(e) => setT({ ...t, logo_text: e.target.value })} className="mt-1 w-full px-3 py-2 rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700" />
        </label>
        <label className="block">
          <span className="text-sm text-gray-600 dark:text-gray-400">Slogan</span>
          <input type="text" value={t.tagline} onChange={(e) => setT({ ...t, tagline: e.target.value })} className="mt-1 w-full px-3 py-2 rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700" />
        </label>
        <label className="block">
          <span className="text-sm text-gray-600 dark:text-gray-400">Primary renk (logo, butonlar)</span>
          <div className="mt-1 flex gap-2 items-center">
            <input type="color" value={t.primary} onChange={(e) => setT({ ...t, primary: e.target.value })} className="w-12 h-10 rounded cursor-pointer border border-gray-200" />
            <input type="text" value={t.primary} onChange={(e) => setT({ ...t, primary: e.target.value })} className="flex-1 px-3 py-2 rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 font-mono text-sm" />
          </div>
        </label>
        <label className="block">
          <span className="text-sm text-gray-600 dark:text-gray-400">Accent renk (gradient ikinci ton)</span>
          <div className="mt-1 flex gap-2 items-center">
            <input type="color" value={t.accent} onChange={(e) => setT({ ...t, accent: e.target.value })} className="w-12 h-10 rounded cursor-pointer border border-gray-200" />
            <input type="text" value={t.accent} onChange={(e) => setT({ ...t, accent: e.target.value })} className="flex-1 px-3 py-2 rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 font-mono text-sm" />
          </div>
        </label>
      </div>
      <div className="rounded-lg p-4 text-white text-lg font-bold" style={{ background: `linear-gradient(to right, ${t.primary}, ${t.accent})` }}>
        {t.logo_text} — {t.tagline}
      </div>
      <button onClick={() => onSave(t as unknown as Record<string, unknown>)} disabled={busy} className="px-4 py-2 rounded-lg bg-blue-500 text-white font-semibold disabled:opacity-50">Kaydet</button>
    </div>
  );
}

function SocialTab({ settings, onSave, busy }: TabProps) {
  const [s, setS] = useState(settings.social);
  const updateField = (platform: keyof typeof s, field: string, value: string | boolean) => {
    setS({ ...s, [platform]: { ...s[platform], [field]: value } });
  };
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-bold">Sosyal Medya Entegrasyonu</h2>
        <p className="text-sm text-gray-500 dark:text-gray-400">API anahtarlarını gir, etkinleştir. API rehberi tabında nasıl alacağını öğrenebilirsin.</p>
      </div>

      <fieldset className="border border-gray-200 dark:border-gray-700 rounded-lg p-4 space-y-3">
        <div className="flex items-center justify-between">
          <legend className="font-semibold flex items-center gap-2">📨 Telegram</legend>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={s.telegram.enabled} onChange={(e) => updateField("telegram", "enabled", e.target.checked)} className="w-4 h-4 accent-blue-600" /> Aktif</label>
        </div>
        <label className="block"><span className="text-xs text-gray-500">Bot Token (BotFather'dan)</span>
          <input type="text" value={s.telegram.bot_token} onChange={(e) => updateField("telegram", "bot_token", e.target.value)} placeholder="123456789:ABCdefGHIjklMNOpqrSTUvwxyz" className="mt-1 w-full px-3 py-2 rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 text-sm font-mono" /></label>
        <label className="block"><span className="text-xs text-gray-500">Chat ID (kanal/grup)</span>
          <input type="text" value={s.telegram.chat_id} onChange={(e) => updateField("telegram", "chat_id", e.target.value)} placeholder="@kanaladim veya -1001234567890" className="mt-1 w-full px-3 py-2 rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 text-sm font-mono" /></label>
      </fieldset>

      <fieldset className="border border-gray-200 dark:border-gray-700 rounded-lg p-4 space-y-3">
        <div className="flex items-center justify-between">
          <legend className="font-semibold flex items-center gap-2">📷 Instagram</legend>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={s.instagram.enabled} onChange={(e) => updateField("instagram", "enabled", e.target.checked)} className="w-4 h-4 accent-blue-600" /> Aktif</label>
        </div>
        <label className="block"><span className="text-xs text-gray-500">Access Token (uzun ömürlü)</span>
          <input type="text" value={s.instagram.access_token} onChange={(e) => updateField("instagram", "access_token", e.target.value)} placeholder="EAA..." className="mt-1 w-full px-3 py-2 rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 text-sm font-mono" /></label>
        <label className="block"><span className="text-xs text-gray-500">Business Account ID</span>
          <input type="text" value={s.instagram.business_account_id} onChange={(e) => updateField("instagram", "business_account_id", e.target.value)} placeholder="17841405..." className="mt-1 w-full px-3 py-2 rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 text-sm font-mono" /></label>
      </fieldset>

      <fieldset className="border border-gray-200 dark:border-gray-700 rounded-lg p-4 space-y-3">
        <div className="flex items-center justify-between">
          <legend className="font-semibold flex items-center gap-2">📘 Facebook</legend>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={s.facebook.enabled} onChange={(e) => updateField("facebook", "enabled", e.target.checked)} className="w-4 h-4 accent-blue-600" /> Aktif</label>
        </div>
        <label className="block"><span className="text-xs text-gray-500">Page Access Token</span>
          <input type="text" value={s.facebook.page_access_token} onChange={(e) => updateField("facebook", "page_access_token", e.target.value)} placeholder="EAA..." className="mt-1 w-full px-3 py-2 rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 text-sm font-mono" /></label>
        <label className="block"><span className="text-xs text-gray-500">Page ID</span>
          <input type="text" value={s.facebook.page_id} onChange={(e) => updateField("facebook", "page_id", e.target.value)} placeholder="123456789" className="mt-1 w-full px-3 py-2 rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 text-sm font-mono" /></label>
      </fieldset>

      <div className="flex gap-2 flex-wrap">
        <button onClick={() => onSave(s as unknown as Record<string, unknown>)} disabled={busy} className="px-4 py-2 rounded-lg bg-blue-500 text-white font-semibold disabled:opacity-50">Kaydet</button>
        <button onClick={async () => {
          const pw = localStorage.getItem("multiscout_admin_pw");
          const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
          const tt = toast.loading("Telegram test mesajı gönderiliyor...");
          const res = await fetch(`${API}/api/admin/test-telegram`, { method: "POST", headers: { "X-ADMIN-PASSWORD": pw || "" } });
          const data = await res.json();
          if (data.ok) toast.success("Telegram OK, mesaj gönderildi", { id: tt });
          else toast.error(data.error || "Gönderilemedi", { id: tt });
        }} className="px-4 py-2 rounded-lg bg-cyan-500 text-white font-semibold">📨 Telegram Test</button>
        <button onClick={async () => {
          const pw = localStorage.getItem("multiscout_admin_pw");
          const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
          const tt = toast.loading("Facebook test gönderiliyor...");
          const res = await fetch(`${API}/api/admin/test-facebook`, { method: "POST", headers: { "X-ADMIN-PASSWORD": pw || "" } });
          const data = await res.json();
          if (data.ok) toast.success("Facebook OK, gönderi paylaşıldı", { id: tt });
          else toast.error(data.error || "Gönderilemedi", { id: tt });
        }} className="px-4 py-2 rounded-lg bg-indigo-500 text-white font-semibold">📘 Facebook Test</button>
        <button onClick={async () => {
          const pw = localStorage.getItem("multiscout_admin_pw");
          const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
          const tt = toast.loading("Instagram test gönderiliyor...");
          const res = await fetch(`${API}/api/admin/test-instagram`, { method: "POST", headers: { "X-ADMIN-PASSWORD": pw || "" } });
          const data = await res.json();
          if (data.ok) toast.success("Instagram OK, paylaşıldı", { id: tt });
          else toast.error(data.error || "Gönderilemedi", { id: tt });
        }} className="px-4 py-2 rounded-lg bg-pink-500 text-white font-semibold">📷 Instagram Test</button>
      </div>
    </div>
  );
}

function AutoShareTab({ settings, onSave, busy }: TabProps) {
  const [s, setS] = useState(settings.auto_share);
  const togglePlatform = (p: string) => {
    const next = s.platforms.includes(p) ? s.platforms.filter((x) => x !== p) : [...s.platforms, p];
    setS({ ...s, platforms: next });
  };
  return (
    <div className="space-y-4">
      <h2 className="text-lg font-bold">Otomatik Paylaşım Kuralları</h2>
      <label className="flex items-center gap-3"><input type="checkbox" checked={s.enabled} onChange={(e) => setS({ ...s, enabled: e.target.checked })} className="w-5 h-5 accent-blue-600" /><span className="text-sm">Otomatik paylaşım aktif</span></label>
      <label className="block">
        <span className="text-sm text-gray-600 dark:text-gray-400">Minimum indirim eşiği (%)</span>
        <input type="number" min="0" max="100" value={s.min_discount} onChange={(e) => setS({ ...s, min_discount: parseInt(e.target.value) || 50 })} className="mt-1 w-full px-3 py-2 rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700" />
      </label>
      <label className="block">
        <span className="text-sm text-gray-600 dark:text-gray-400">Günlük maksimum paylaşım</span>
        <input type="number" min="1" value={s.max_per_day} onChange={(e) => setS({ ...s, max_per_day: parseInt(e.target.value) || 10 })} className="mt-1 w-full px-3 py-2 rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700" />
      </label>
      <div>
        <span className="text-sm text-gray-600 dark:text-gray-400 block mb-2">Hangi platformlarda paylaşılsın?</span>
        <div className="flex gap-2 flex-wrap">
          {["telegram", "instagram", "facebook"].map((p) => (
            <button key={p} onClick={() => togglePlatform(p)} className={`px-3 py-1.5 rounded-full text-sm font-medium ${s.platforms.includes(p) ? "bg-blue-500 text-white" : "bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300 border border-gray-200 dark:border-gray-700"}`}>{p}</button>
          ))}
        </div>
      </div>
      <div className="flex gap-2 flex-wrap">
        <button onClick={() => onSave(s as unknown as Record<string, unknown>)} disabled={busy} className="px-4 py-2 rounded-lg bg-blue-500 text-white font-semibold disabled:opacity-50">Kaydet</button>
        <button onClick={async () => {
          const pw = localStorage.getItem("multiscout_admin_pw");
          const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
          const tt = toast.loading("Paylaşım tetikleniyor...");
          const res = await fetch(`${API}/api/admin/trigger-share`, { method: "POST", headers: { "X-ADMIN-PASSWORD": pw || "" } });
          if (res.ok) {
            const data = await res.json();
            toast.success(`${data.shared} deal paylaşıldı`, { id: tt });
          } else {
            toast.error("Tetiklenemedi", { id: tt });
          }
        }} className="px-4 py-2 rounded-lg bg-purple-500 text-white font-semibold">🚀 Şimdi Paylaş (test)</button>
      </div>
    </div>
  );
}

function MaintenanceTab({ settings, onSave, busy }: TabProps) {
  const [m, setM] = useState(settings.maintenance);
  return (
    <div className="space-y-4">
      <h2 className="text-lg font-bold">Bakım Modu</h2>
      <p className="text-sm text-gray-500 dark:text-gray-400">Aktifken kullanıcılar bakım sayfası görür, deal'ler gizlenir.</p>
      <label className="flex items-center gap-3"><input type="checkbox" checked={m.enabled} onChange={(e) => setM({ ...m, enabled: e.target.checked })} className="w-5 h-5 accent-rose-600" /><span className="text-sm">Bakım modu aktif</span></label>
      <label className="block">
        <span className="text-sm text-gray-600 dark:text-gray-400">Mesaj</span>
        <textarea value={m.message} onChange={(e) => setM({ ...m, message: e.target.value })} rows={3} className="mt-1 w-full px-3 py-2 rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700" />
      </label>
      <button onClick={() => onSave(m as unknown as Record<string, unknown>)} disabled={busy} className="px-4 py-2 rounded-lg bg-blue-500 text-white font-semibold disabled:opacity-50">Kaydet</button>
    </div>
  );
}

/** Tüm admin sayfalarında üstte görünen canlı tarama durum çubuğu */
function GlobalStatusBar({ onNavigate }: { onNavigate?: (tab: string) => void }) {
  const [statuses, setStatuses] = useState<Record<string, PlatformStatus>>({});
  const [global, setGlobal] = useState<{ status: string; updated_at: string } | null>(null);

  useEffect(() => {
    const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    let stopped = false;
    const fetchStatus = async () => {
      try {
        const res = await fetch(`${API}/api/scrape-all-status`);
        if (!res.ok) return;
        const json = await res.json();
        if (stopped) return;
        const d = json.data || {};
        const { status, updated_at } = d;
        const platforms = { ...d };
        delete platforms.status; delete platforms.message; delete platforms.updated_at;
        setGlobal({ status: status || "idle", updated_at: updated_at || "" });
        setStatuses(platforms as Record<string, PlatformStatus>);
      } catch {}
    };
    fetchStatus();
    const interval = setInterval(fetchStatus, 5000);
    return () => { stopped = true; clearInterval(interval); };
  }, []);

  const running = Object.entries(statuses).filter(([, v]) => v?.status === "running");
  const errored = Object.entries(statuses).filter(([, v]) => v?.status === "error");
  const completed = Object.entries(statuses).filter(([, v]) => v?.status === "completed").length;

  if (running.length === 0 && errored.length === 0) {
    // Idle — kompakt yeşil dot + sayı
    return (
      <div className="mb-4 flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
        <span className="w-2 h-2 rounded-full bg-green-500" />
        <span>{completed > 0 ? `${completed} platform son taramayı tamamladı` : "Tarama yapılmıyor"}</span>
        {global?.updated_at && (
          <span className="opacity-60">· {new Date(global.updated_at).toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" })}</span>
        )}
      </div>
    );
  }

  return (
    <button
      onClick={() => onNavigate?.("logs")}
      className={`w-full mb-4 px-4 py-2.5 rounded-lg border text-left transition cursor-pointer ${
        errored.length > 0
          ? "bg-rose-50 dark:bg-rose-900/20 border-rose-300 dark:border-rose-700/50 hover:border-rose-400"
          : "bg-blue-50 dark:bg-blue-900/20 border-blue-300 dark:border-blue-700/50 hover:border-blue-400"
      }`}
    >
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2">
          <span className={`w-2.5 h-2.5 rounded-full ${running.length > 0 ? "bg-blue-500 animate-pulse" : "bg-rose-500"}`} />
          <span className="text-sm font-semibold">
            {running.length > 0 && `${running.length} platform taranıyor`}
            {running.length > 0 && errored.length > 0 && " · "}
            {errored.length > 0 && `${errored.length} platformda hata`}
          </span>
        </div>
        <div className="flex items-center gap-1.5 flex-wrap">
          {running.slice(0, 8).map(([p]) => (
            <span key={p} className="text-[10px] px-2 py-0.5 rounded-full bg-white dark:bg-gray-900 border border-blue-200 dark:border-blue-700/40 text-blue-700 dark:text-blue-300 font-medium">
              {STORE_LABELS[p] || p}
            </span>
          ))}
          {running.length > 8 && (
            <span className="text-[10px] px-2 py-0.5 rounded-full bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 text-gray-500">
              +{running.length - 8}
            </span>
          )}
          <span className="text-[10px] text-gray-500 ml-1">Loglara git →</span>
        </div>
      </div>
    </button>
  );
}

/** Backend stdout/stderr ring buffer'ından log akışı */
function LogsTab() {
  const [logs, setLogs] = useState<Array<{ ts: string; platform: string | null; src: string; msg: string }>>([]);
  const [filter, setFilter] = useState("");
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [autoScroll, setAutoScroll] = useState(true);
  const [paused, setPaused] = useState(false);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!autoRefresh) return;
    let stopped = false;
    const fetchLogs = async () => {
      if (paused) return;
      try {
        const pw = typeof window !== "undefined" ? localStorage.getItem("multiscout_admin_pw") : null;
        if (!pw) return;
        const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
        const url = `${API}/api/admin/logs?lines=300${filter ? `&platform=${encodeURIComponent(filter)}` : ""}`;
        const res = await fetch(url, { headers: { "X-ADMIN-PASSWORD": pw } });
        if (!res.ok || stopped) return;
        const json = await res.json();
        setLogs(json.data?.lines || []);
      } catch {}
    };
    fetchLogs();
    const interval = setInterval(fetchLogs, 2500);
    return () => { stopped = true; clearInterval(interval); };
  }, [autoRefresh, filter, paused]);

  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs, autoScroll]);

  const platforms = Array.from(new Set(logs.map(l => l.platform).filter((p): p is string => !!p))).sort();
  const filtered = filter ? logs.filter(l => l.platform === filter.toLowerCase()) : logs;

  return (
    <div className="space-y-3">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <h2 className="text-lg font-bold">Loglar</h2>
          <p className="text-sm text-gray-500 dark:text-gray-400">Backend stdout/stderr son 300 satır. 2.5 sn'de bir otomatik yenilenir.</p>
        </div>
        <div className="flex gap-2 items-center flex-wrap">
          <label className="flex items-center gap-1.5 text-xs">
            <input type="checkbox" checked={autoRefresh} onChange={(e) => setAutoRefresh(e.target.checked)} className="accent-blue-600" />
            <span>Otomatik yenile</span>
          </label>
          <label className="flex items-center gap-1.5 text-xs">
            <input type="checkbox" checked={autoScroll} onChange={(e) => setAutoScroll(e.target.checked)} className="accent-blue-600" />
            <span>Auto scroll</span>
          </label>
          <button
            onClick={() => setPaused(!paused)}
            className={`px-3 py-1 rounded text-xs font-medium ${paused ? "bg-green-500 text-white" : "bg-gray-200 dark:bg-gray-700"}`}
          >
            {paused ? "▶ Devam" : "⏸ Duraklat"}
          </button>
        </div>
      </div>

      {/* Platform filter chips */}
      {platforms.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          <button
            onClick={() => setFilter("")}
            className={`px-2 py-0.5 rounded-full text-[10px] font-medium ${
              !filter
                ? "bg-blue-500 text-white"
                : "bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400"
            }`}
          >
            Tümü ({logs.length})
          </button>
          {platforms.map(p => {
            const cnt = logs.filter(l => l.platform === p).length;
            const isActive = filter.toLowerCase() === p;
            return (
              <button
                key={p}
                onClick={() => setFilter(isActive ? "" : p)}
                className={`px-2 py-0.5 rounded-full text-[10px] font-medium ${
                  isActive
                    ? "bg-blue-500 text-white"
                    : "bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-200"
                }`}
              >
                {STORE_LABELS[p] || p} ({cnt})
              </button>
            );
          })}
        </div>
      )}

      {/* Log viewer */}
      <div
        ref={scrollRef}
        className="bg-gray-950 text-gray-200 rounded-lg p-3 font-mono text-[11px] leading-relaxed overflow-auto"
        style={{ maxHeight: "70vh", minHeight: "400px" }}
      >
        {filtered.length === 0 && (
          <div className="text-gray-500 italic">Henüz log yok. {filter && `"${filter}" için kayıt yok.`}</div>
        )}
        {filtered.map((l, i) => {
          const ts = l.ts ? new Date(l.ts).toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit", second: "2-digit" }) : "";
          const isErr = l.src === "err" || /HATA|Error|error|Traceback|hata/.test(l.msg);
          return (
            <div key={i} className={`flex gap-2 ${isErr ? "text-rose-300" : ""}`}>
              <span className="text-gray-500 shrink-0">{ts}</span>
              {l.platform && (
                <span className="text-cyan-400 shrink-0">[{l.platform}]</span>
              )}
              <span className="break-all whitespace-pre-wrap">{l.msg.replace(/^\[[\w]+\]\s*/, "")}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function DocsTab() {
  return (
    <div className="space-y-6 text-sm">
      <div>
        <h2 className="text-lg font-bold mb-2">📚 API Anahtarları Nasıl Alınır?</h2>
        <p className="text-gray-500 dark:text-gray-400">Otomatik paylaşım için her platforma API anahtarı bağlamalısın. Aşağıda her birinin adımlarını bulacaksın.</p>
      </div>

      <section className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-700/50 rounded-lg p-4">
        <h3 className="font-bold text-lg mb-2 flex items-center gap-2">📨 Telegram (en kolay — 5 dk)</h3>
        <ol className="list-decimal list-inside space-y-2 text-gray-700 dark:text-gray-200">
          <li>Telegram'da <a href="https://t.me/BotFather" target="_blank" rel="noreferrer" className="text-blue-600 underline">@BotFather</a> ile sohbet aç.</li>
          <li><code className="bg-white dark:bg-gray-800 px-1.5 py-0.5 rounded">/newbot</code> yaz, isim ve username ver (örn: <code>MultiScoutDealsBot</code>).</li>
          <li>BotFather sana bir <strong>token</strong> verir: <code className="text-xs">123456789:ABCdef...</code> → Sosyal Medya tabında <em>Bot Token</em>'a yapıştır.</li>
          <li>Bir Telegram <strong>kanalı/grubu</strong> oluştur (örn: <code>@firsatlar_kanal</code>) ve botu admin yap.</li>
          <li>Kanal username'i (<code>@firsatlar_kanal</code>) ya da numeric chat ID'yi <em>Chat ID</em>'ye yaz.</li>
          <li>Bot, kanala mesaj yollayabilecek. <strong>Otomatik Paylaşım</strong> tabında etkinleştir.</li>
        </ol>
        <details className="mt-3">
          <summary className="cursor-pointer text-blue-600 font-medium">Numeric Chat ID nasıl bulunur?</summary>
          <p className="mt-2 text-gray-600 dark:text-gray-300">Kanal/gruba bir mesaj yolla, sonra <code>https://api.telegram.org/bot&lt;TOKEN&gt;/getUpdates</code> URL'sini ziyaret et — <code>chat.id</code> alanını gör.</p>
        </details>
        <p className="mt-3 text-xs text-gray-500">Ücretsiz, sınırsız bot mesajı (genelde dakikada 30 limit). API: <a href="https://core.telegram.org/bots/api" className="text-blue-600 underline" target="_blank" rel="noreferrer">core.telegram.org/bots/api</a></p>
      </section>

      <section className="bg-pink-50 dark:bg-pink-900/20 border border-pink-200 dark:border-pink-700/50 rounded-lg p-4">
        <h3 className="font-bold text-lg mb-2 flex items-center gap-2">📷 Instagram Business (~30 dk)</h3>
        <ol className="list-decimal list-inside space-y-2 text-gray-700 dark:text-gray-200">
          <li>Instagram hesabını <strong>Profesyonel hesaba</strong> (Business/Creator) çevir.</li>
          <li>Bir Facebook <strong>Sayfası</strong> oluştur ve Instagram hesabını bu sayfaya bağla (Instagram → Profil → Düzenle → Sayfa).</li>
          <li><a href="https://developers.facebook.com" target="_blank" rel="noreferrer" className="text-pink-600 underline">developers.facebook.com</a>'a git, hesap aç (geliştirici onayı bazen 1-2 gün sürer).</li>
          <li>Yeni bir Uygulama oluştur (App type: Business). <strong>App ID</strong> ve <strong>App Secret</strong>'i not et.</li>
          <li>App'e <strong>Instagram Graph API</strong> ürününü ekle.</li>
          <li><a href="https://developers.facebook.com/tools/explorer" target="_blank" rel="noreferrer" className="text-pink-600 underline">Graph API Explorer</a>'da token üret, izinleri seç: <code>instagram_basic, instagram_content_publish, pages_show_list, pages_read_engagement</code>.</li>
          <li>Kısa ömürlü token'ı <strong>uzun ömürlü</strong> (60 gün) token'a çevir: <code className="text-xs">GET /oauth/access_token?grant_type=fb_exchange_token&...</code></li>
          <li>Business Account ID'yi öğren: <code className="text-xs">GET /me/accounts</code> → her sayfanın <code>instagram_business_account.id</code>'sini gör.</li>
          <li>Sosyal Medya tabında <em>Access Token</em> ve <em>Business Account ID</em>'yi yapıştır.</li>
        </ol>
        <p className="mt-3 text-xs text-gray-500">Token'ı 60 günde bir yenilemen gerek. API doc: <a href="https://developers.facebook.com/docs/instagram-api" className="text-pink-600 underline" target="_blank" rel="noreferrer">Instagram Graph API</a></p>
      </section>

      <section className="bg-indigo-50 dark:bg-indigo-900/20 border border-indigo-200 dark:border-indigo-700/50 rounded-lg p-4">
        <h3 className="font-bold text-lg mb-2 flex items-center gap-2">📘 Facebook Sayfa (~20 dk)</h3>
        <ol className="list-decimal list-inside space-y-2 text-gray-700 dark:text-gray-200">
          <li>Facebook'ta paylaşım yapacağın <strong>Sayfa</strong>nı belirle (Profil değil!).</li>
          <li>Instagram adımlarındaki gibi <a href="https://developers.facebook.com" target="_blank" rel="noreferrer" className="text-indigo-600 underline">developers.facebook.com</a>'da app oluştur.</li>
          <li>App'e <strong>Facebook Login + Pages API</strong> ekle.</li>
          <li>Graph API Explorer'da <code>pages_manage_posts, pages_read_engagement</code> izinleriyle token al.</li>
          <li><strong>Page Access Token</strong> al: <code className="text-xs">GET /me/accounts</code> → sayfanın <code>access_token</code>'unu kopyala (kullanıcı token'ından farklı).</li>
          <li>Sayfa ID'sini de al (<code>id</code> alanı).</li>
          <li>Sosyal Medya tabında <em>Page Access Token</em> ve <em>Page ID</em>'yi yapıştır.</li>
        </ol>
        <p className="mt-3 text-xs text-gray-500">Page token'lar genelde uzun ömürlüdür (Instagram'dan kalıcı). API doc: <a href="https://developers.facebook.com/docs/pages-api" className="text-indigo-600 underline" target="_blank" rel="noreferrer">Pages API</a></p>
      </section>

      <section className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700/50 rounded-lg p-4">
        <h3 className="font-bold mb-2">⚠️ Önemli Notlar</h3>
        <ul className="list-disc list-inside space-y-1 text-gray-700 dark:text-gray-200">
          <li>Token'ları kimseyle paylaşma; bu admin paneli localStorage'da saklıyor — paylaşım için backend'de kullanılacak (token'lar JSON'da saklanır).</li>
          <li>Üretim ortamında <code>data/admin_settings.json</code> dosyasına dosya sistemi izinleri ver veya environment variables kullan.</li>
          <li>Instagram rate limit: günlük 25 resim/video paylaşım önerilir.</li>
          <li>Facebook ve Instagram'da App'in onaylanması gerekebilir; geliştirici modunda sadece sen test edebilirsin.</li>
          <li>Token süresi dolduğunda otomatik paylaşım çalışmaz — bildirim için Maintenance tabında uyarı ekleyebilirsin.</li>
        </ul>
      </section>
    </div>
  );
}
