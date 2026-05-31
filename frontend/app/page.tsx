"use client";

import { useEffect, useMemo, useState, useCallback } from "react";
import Image from "next/image";
import { AnimatePresence, motion } from "framer-motion";
import { toast } from "sonner";
import SidebarItem from "../components/Sidebar";
import { DealGridSkeleton } from "../components/DealCardSkeleton";
import ThemeToggle from "../components/ThemeToggle";
import LanguageToggle from "../components/LanguageToggle";
import PriceHistoryChart from "../components/PriceHistoryChart";
import FilterSheet from "../components/FilterSheet";
import { isBoycotted, refreshBoycottList, getBoycottMeta } from "../lib/boycott";
import { getFavorites, toggleFavorite } from "../lib/favorites";
import { parsePrice, computeTrend, extractBrand, toCsv, downloadCsv } from "../lib/helpers";
import { useI18n } from "../lib/i18n";
import { getPublicStoresStatus } from "../lib/admin";
import { checkAlarms } from "../lib/alarms";
import AlarmButton from "../components/AlarmButton";
import AiSummary from "../components/AiSummary";
import VoiceSearch from "../components/VoiceSearch";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type CategoryNode = string[] | { [key: string]: CategoryNode };

interface PriceHistoryEntry {
  date: string;
  price: string;
  discount_percentage: number;
}

interface Deal {
  title: string;
  price?: string;
  discount_percentage?: number;
  link?: string;
  image?: string;
  category?: string;
  deal_score?: number;
  price_history?: PriceHistoryEntry[];
  last_updated?: string;
  platform?: string;
}

type PlatformKey =
  | "hepsi" | "amazon" | "trendyol" | "hepsiburada" | "n11"
  | "pazarama" | "ciceksepeti" | "vatan" | "teknosa" | "decathlon" | "steam" | "mediamarkt" | "defacto" | "gratis"
  | "a101" | "bim" | "sok" | "migros" | "carrefoursa" | "tarimkredi"
  | "hakmarexpress" | "macrocenter" | "bizimtoptan" | "peynircibaba"
  | "lcwaikiki" | "koton" | "mavi"
  | "boyner" | "penti" | "watsons" | "dr"
  | "karaca" | "englishhome" | "idefix" | "tchibo"
  | "mudo" | "madamecoco" | "vivense"
  | "tepehome" | "skechers"
  | "toyzz" | "yargici" | "kitapyurdu"
  | "pttavm" | "sportive" | "newbalance"
  | "flo" | "hummel" | "evidea"
  | "beko" | "arcelik" | "vestel"
  | "network" | "northface"
  | "mac" | "apple"
  | "saatvesaat" | "altinbas" | "pasabahce"
  | "akakce" | "ramsey" | "atasay" | "reebok" | "sarar" | "huawei" | "lego"
  | "casper" | "monster";
type BoycottMode = "highlight" | "hide" | "show";

const PLATFORM_LABELS: Record<PlatformKey, string> = {
  hepsi: "Hepsi",
  amazon: "Amazon",
  trendyol: "Trendyol",
  hepsiburada: "Hepsiburada",
  n11: "N11",
  pazarama: "Pazarama",
  ciceksepeti: "Çiçek Sepeti",
  vatan: "Vatan",
  teknosa: "Teknosa",
  decathlon: "Decathlon",
  steam: "Steam",
  mediamarkt: "MediaMarkt",
  defacto: "Defacto",
  gratis: "Gratis",
  a101: "A101",
  bim: "BİM",
  sok: "ŞOK",
  migros: "MİGROS",
  carrefoursa: "CarrefourSA",
  tarimkredi: "Tarım Kredi",
  hakmarexpress: "Hakmar Express",
  macrocenter: "Macrocenter",
  bizimtoptan: "Bizim Toptan",
  peynircibaba: "Peynirci Baba",
  lcwaikiki: "LC Waikiki",
  koton: "Koton",
  mavi: "Mavi",
  boyner: "Boyner",
  penti: "Penti",
  watsons: "Watsons",
  dr: "D&R",
  karaca: "Karaca",
  englishhome: "English Home",
  idefix: "Idefix",
  tchibo: "Tchibo",
  mudo: "Mudo",
  madamecoco: "Madame Coco",
  vivense: "Vivense",
  tepehome: "Tepe Home",
  skechers: "Skechers",
  toyzz: "Toyzz Shop",
  yargici: "Yargıcı",
  kitapyurdu: "Kitapyurdu",
  pttavm: "PttAVM",
  sportive: "Sportive",
  newbalance: "New Balance",
  flo: "FLO",
  hummel: "Hummel",
  evidea: "Evidea",
  beko: "Beko",
  arcelik: "Arçelik",
  vestel: "Vestel",
  network: "Network",
  northface: "The North Face",
  mac: "MAC Cosmetics",
  apple: "Apple",
  saatvesaat: "Saat ve Saat",
  altinbas: "Altınbaş",
  pasabahce: "Paşabahçe",
  akakce: "Akakçe",
  ramsey: "Ramsey",
  atasay: "Atasay",
  reebok: "Reebok",
  sarar: "Sarar",
  huawei: "Huawei",
  lego: "Lego",
  casper: "Casper",
  monster: "Monster",
};

const ALL_PLATFORM_KEYS: PlatformKey[] = [
  "hepsi", "amazon", "trendyol", "hepsiburada", "n11",
  "pazarama", "ciceksepeti", "vatan", "teknosa", "decathlon", "steam", "mediamarkt", "defacto", "gratis",
  "a101", "bim", "sok", "migros", "carrefoursa", "tarimkredi",
  "hakmarexpress", "macrocenter", "bizimtoptan", "peynircibaba",
  "lcwaikiki", "koton", "mavi",
  "boyner", "penti", "watsons", "dr",
  "karaca", "englishhome", "idefix", "tchibo",
  "mudo", "madamecoco", "vivense",
  "tepehome", "skechers",
  "toyzz", "yargici", "kitapyurdu",
  "pttavm", "sportive", "newbalance",
  "flo", "hummel", "evidea",
  "beko", "arcelik", "vestel",
  "network", "northface",
  "mac", "apple",
  "saatvesaat", "altinbas", "pasabahce",
  "akakce", "ramsey", "atasay", "reebok", "sarar", "huawei", "lego",
  "casper", "monster",
];

const BOYCOTT_MODES: { key: BoycottMode; tKey: string; icon: string }[] = [
  { key: "highlight", tKey: "boycott.highlight", icon: "⚠️" },
  { key: "hide", tKey: "boycott.hide", icon: "🚫" },
  { key: "show", tKey: "boycott.show", icon: "👁" },
];

const formatTimestamp = (value: string, locale: string) => {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(locale === "en" ? "en-US" : "tr-TR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
};

function PlatformPills({ selected, onSelect, layoutId, platforms }: { selected: PlatformKey; onSelect: (p: PlatformKey) => void; layoutId: string; platforms: PlatformKey[] }) {
  return (
    <div className="flex gap-2 overflow-x-auto pb-1 -mx-1 px-1 snap-x snap-mandatory scroll-smooth">
      {platforms.map((p) => (
        <motion.button
          key={p}
          onClick={() => onSelect(p)}
          whileTap={{ scale: 0.95 }}
          className={`relative shrink-0 snap-start px-3.5 py-1.5 rounded-full text-sm font-medium transition whitespace-nowrap ${
            selected === p
              ? "text-white"
              : "bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-200 border border-gray-200 dark:border-gray-700 hover:border-blue-400"
          }`}
        >
          {selected === p && (
            <motion.span
              layoutId={layoutId}
              className="absolute inset-0 bg-gradient-to-r from-blue-500 to-blue-600 rounded-full shadow-sm"
              transition={{ type: "spring", stiffness: 500, damping: 35 }}
            />
          )}
          <span className="relative z-10">{PLATFORM_LABELS[p]}</span>
        </motion.button>
      ))}
    </div>
  );
}

export default function Home() {
  const { t, locale } = useI18n();
  const [deals, setDeals] = useState<Deal[]>([]);
  const [totalDeals, setTotalDeals] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [manualScraping, setManualScraping] = useState(false);
  const [categoryTree, setCategoryTree] = useState<{ [key: string]: CategoryNode } | null>(null);
  const [categoryCounts, setCategoryCounts] = useState<Record<string, number>>({});
  const [categoryTotal, setCategoryTotal] = useState(0);
  const [categoryQuery, setCategoryQuery] = useState("");
  const [selectedCategory, setSelectedCategory] = useState("");
  const [selectedPlatform, setSelectedPlatform] = useState<PlatformKey>("hepsi");
  const [selectedSort, setSelectedSort] = useState("last_updated");
  const [scrolled, setScrolled] = useState(false);
  const [boycottMode, setBoycottMode] = useState<BoycottMode>("highlight");
  const [filterOpen, setFilterOpen] = useState(false);
  const [categoryOpen, setCategoryOpen] = useState(false);
  const [boycottMeta, setBoycottMeta] = useState(() => getBoycottMeta());
  const [enabledStores, setEnabledStores] = useState<Set<string>>(new Set(ALL_PLATFORM_KEYS));
  const [maintenanceMsg, setMaintenanceMsg] = useState<string | null>(null);
  const [brandText, setBrandText] = useState<{ logo: string; tagline: string }>({ logo: "MultiScout", tagline: "Fırsat Takipçisi" });

  // Paket 3 state
  const [searchQuery, setSearchQuery] = useState("");
  const [favoritesOnly, setFavoritesOnly] = useState(false);
  const [favorites, setFavoritesState] = useState<Set<string>>(new Set());
  const [selectedBrands, setSelectedBrands] = useState<Set<string>>(new Set());
  const [priceMin, setPriceMin] = useState<number | null>(null);
  const [priceMax, setPriceMax] = useState<number | null>(null);
  const [urlInitialized, setUrlInitialized] = useState(false);

  // Load URL state on mount
  /* eslint-disable react-hooks/set-state-in-effect */
  useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    const p = params.get("platform"); if (p && ALL_PLATFORM_KEYS.includes(p as PlatformKey)) setSelectedPlatform(p as PlatformKey);
    const c = params.get("category"); if (c) setSelectedCategory(c);
    const s = params.get("sort"); if (s) setSelectedSort(s);
    const q = params.get("q"); if (q) setSearchQuery(q);
    const b = params.get("boycott"); if (b === "hide" || b === "show" || b === "highlight") setBoycottMode(b);
    const f = params.get("fav"); if (f === "1") setFavoritesOnly(true);
    const br = params.get("brands"); if (br) setSelectedBrands(new Set(br.split(",").filter(Boolean)));
    const pmin = params.get("pmin"); if (pmin) setPriceMin(parseFloat(pmin));
    const pmax = params.get("pmax"); if (pmax) setPriceMax(parseFloat(pmax));

    setFavoritesState(getFavorites());
    const stored = localStorage.getItem("boycottMode");
    if (stored === "hide" || stored === "show" || stored === "highlight") setBoycottMode(stored);
    setUrlInitialized(true);
  }, []);
  /* eslint-enable react-hooks/set-state-in-effect */

  // Sync URL on filter changes
  useEffect(() => {
    if (!urlInitialized || typeof window === "undefined") return;
    const params = new URLSearchParams();
    if (selectedPlatform !== "hepsi") params.set("platform", selectedPlatform);
    if (selectedCategory) params.set("category", selectedCategory);
    if (selectedSort !== "last_updated") params.set("sort", selectedSort);
    if (searchQuery) params.set("q", searchQuery);
    if (boycottMode !== "highlight") params.set("boycott", boycottMode);
    if (favoritesOnly) params.set("fav", "1");
    if (selectedBrands.size > 0) params.set("brands", [...selectedBrands].join(","));
    if (priceMin !== null) params.set("pmin", priceMin.toString());
    if (priceMax !== null) params.set("pmax", priceMax.toString());
    const qs = params.toString();
    const newUrl = qs ? `?${qs}` : window.location.pathname;
    window.history.replaceState(null, "", newUrl);
  }, [urlInitialized, selectedPlatform, selectedCategory, selectedSort, searchQuery, boycottMode, favoritesOnly, selectedBrands, priceMin, priceMax]);

  useEffect(() => {
    if (typeof window !== "undefined") localStorage.setItem("boycottMode", boycottMode);
  }, [boycottMode]);

  const fetchDeals = useCallback((category: string, platform: PlatformKey, isNew: boolean, sortBy: string) => {
    if (isNew) setLoading(true);
    else setLoadingMore(true);

    const skip = isNew ? 0 : deals.length;
    fetch(`${API_URL}/api/deals?platform=${platform}&category=${category}&skip=${skip}&limit=30&sort_by=${sortBy}`)
      .then((res) => res.json())
      .then((data) => {
        if (data.status === "success") {
          setDeals((prev) => (isNew ? data.data : [...prev, ...data.data]));
          setTotalDeals(data.total);
          // Fiyat alarmlarını kontrol et
          const triggered = checkAlarms(data.data || []);
          if (triggered.length > 0) {
            toast.success(`🔔 ${triggered.length} fiyat alarmı tetiklendi!`);
          }
        } else if (data.message) {
          toast.error(data.message);
        }
      })
      .catch((err) => {
        console.error(err);
        toast.error(t("loading.products") + " — error");
      })
      .finally(() => {
        setLoading(false);
        setLoadingMore(false);
      });
  }, [deals.length, t]);

  const selectCategory = (category: string) => {
    setSelectedCategory(category);
    setDeals([]); setTotalDeals(0); setCategoryOpen(false);
    fetchDeals(category, selectedPlatform, true, selectedSort);
  };
  const selectPlatform = (platform: PlatformKey) => {
    setSelectedPlatform(platform);
    setDeals([]); setTotalDeals(0);
    setFilterOpen(false);
    fetchDeals(selectedCategory, platform, true, selectedSort);
  };
  const selectSort = (sort: string) => {
    setSelectedSort(sort);
    setDeals([]); setTotalDeals(0);
    setFilterOpen(false);
    fetchDeals(selectedCategory, selectedPlatform, true, sort);
  };

  const handleToggleFavorite = (link: string) => {
    const next = toggleFavorite(link);
    setFavoritesState(new Set(next));
  };

  useEffect(() => {
    const handleScroll = () => {
      setScrolled(window.scrollY > 10);
      if (window.innerHeight + window.scrollY >= document.body.offsetHeight - 500) {
        if (!loadingMore && deals.length < totalDeals) {
          fetchDeals(selectedCategory, selectedPlatform, false, selectedSort);
        }
      }
    };
    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [deals.length, totalDeals, loadingMore, selectedCategory, selectedPlatform, selectedSort]);

  // Platform değişince kategori ağacını + sayıları yeniden çek
  useEffect(() => {
    Promise.all([
      fetch(`${API_URL}/api/category-tree?platform=${selectedPlatform}`).then((r) => r.json()),
      fetch(`${API_URL}/api/category-counts?platform=${selectedPlatform}`).then((r) => r.json()),
    ])
      .then(([tree, counts]) => {
        if (tree?.status === "success") {
          setCategoryTree(tree.data);
          const flat: string[] = Array.isArray(tree.categories) ? tree.categories : [];
          if (flat.length && selectedCategory && !flat.includes(selectedCategory)) {
            const next = flat[0];
            setSelectedCategory(next);
            setDeals([]); setTotalDeals(0);
            fetchDeals(next, selectedPlatform, true, selectedSort);
          }
        }
        if (counts?.status === "success") {
          setCategoryCounts(counts.data || {});
          setCategoryTotal(counts.total || 0);
        }
      })
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedPlatform]);

  useEffect(() => {
    refreshBoycottList(false).then(() => setBoycottMeta(getBoycottMeta()));

    getPublicStoresStatus().then((s) => {
      if (!s) return;
      const en = new Set<string>(["hepsi", ...s.enabled]);
      setEnabledStores(en);
      if (s.maintenance?.enabled) setMaintenanceMsg(s.maintenance.message || "Bakım modundayız.");
      if (s.theme) setBrandText({ logo: s.theme.logo_text || "MultiScout", tagline: s.theme.tagline || "Fırsat Takipçisi" });
      if (s.theme?.primary && typeof document !== "undefined") {
        document.documentElement.style.setProperty("--brand-primary", s.theme.primary);
        document.documentElement.style.setProperty("--brand-accent", s.theme.accent || s.theme.primary);
      }
    });

    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchDeals(selectedCategory, selectedPlatform, true, selectedSort);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const scrapeAllCategories = async () => {
    try {
      setManualScraping(true);
      const platformParam = selectedPlatform === "hepsi" ? "all" : selectedPlatform;
      const toastId = toast.loading(`${PLATFORM_LABELS[selectedPlatform]} ${t("header.scanning")}`);
      const startRes = await fetch(`${API_URL}/api/scrape-all?platform=${platformParam}`, { method: "POST" });
      if (!startRes.ok) {
        const err = await startRes.json().catch(() => ({}));
        toast.error(err.detail || "Error", { id: toastId });
        setManualScraping(false); return;
      }
      const checkStatus = setInterval(async () => {
        try {
          const res = await fetch(`${API_URL}/api/scrape-all-status`);
          const data = await res.json();
          const top = data?.data?.status;
          if (top === "completed") {
            clearInterval(checkStatus);
            setManualScraping(false);
            toast.success("✓", { id: toastId });
            fetchDeals(selectedCategory, selectedPlatform, true, selectedSort);
          } else if (top === "error") {
            clearInterval(checkStatus);
            setManualScraping(false);
            toast.error(data?.data?.message || "Error", { id: toastId });
          }
        } catch { /* keep polling */ }
      }, 5000);
    } catch {
      setManualScraping(false);
      toast.error("Error");
    }
  };

  // Apply all filters in memory
  const { visibleDeals, hiddenBoycottCount, allBrands, priceBounds } = useMemo(() => {
    const visible: Deal[] = [];
    let hidden = 0;
    const brandCounts = new Map<string, number>();
    let dMin = Infinity, dMax = 0;

    const q = searchQuery.trim().toLowerCase();

    for (const d of deals) {
      const price = parsePrice(d.price);
      if (price > 0) { dMin = Math.min(dMin, price); dMax = Math.max(dMax, price); }
      const brand = extractBrand(d.title);
      if (brand) brandCounts.set(brand, (brandCounts.get(brand) || 0) + 1);

      const b = isBoycotted(d.title);
      if (boycottMode === "hide" && b) { hidden += 1; continue; }
      if (q && !d.title.toLowerCase().includes(q)) continue;
      if (favoritesOnly && !favorites.has(d.link || "")) continue;
      if (selectedBrands.size > 0 && brand && !selectedBrands.has(brand)) continue;
      if (priceMin !== null && price > 0 && price < priceMin) continue;
      if (priceMax !== null && price > 0 && price > priceMax) continue;
      visible.push(d);
    }

    const brands = [...brandCounts.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, 30);

    return {
      visibleDeals: visible,
      hiddenBoycottCount: hidden,
      allBrands: brands,
      priceBounds: { min: dMin === Infinity ? 0 : Math.floor(dMin), max: Math.ceil(dMax) },
    };
  }, [deals, boycottMode, searchQuery, favoritesOnly, favorites, selectedBrands, priceMin, priceMax]);

  const clearAllFilters = () => {
    setSearchQuery("");
    setFavoritesOnly(false);
    setSelectedBrands(new Set());
    setPriceMin(null);
    setPriceMax(null);
  };

  const exportCsv = () => {
    if (visibleDeals.length === 0) {
      toast.error("Boş liste");
      return;
    }
    const rows = visibleDeals.map((d) => ({
      title: d.title,
      price: d.price ?? "",
      discount_percentage: d.discount_percentage ?? 0,
      platform: d.platform ?? "",
      category: d.category ?? "",
      link: d.link ?? "",
      last_updated: d.last_updated ?? "",
    }));
    downloadCsv(`multiscout-${selectedPlatform}-${Date.now()}.csv`, toCsv(rows));
    toast.success("CSV indirildi");
  };

  const shareUrl = async () => {
    if (typeof window === "undefined") return;
    try {
      await navigator.clipboard.writeText(window.location.href);
      toast.success(t("common.copied"));
    } catch {
      toast.error("Copy failed");
    }
  };

  const cardVariants = {
    hidden: { opacity: 0, y: 20 },
    visible: (i: number) => ({
      opacity: 1, y: 0,
      transition: { delay: Math.min(i, 12) * 0.04, duration: 0.35, ease: [0.16, 1, 0.3, 1] as const },
    }),
  };

  const activeFilterCount = (searchQuery ? 1 : 0) + (favoritesOnly ? 1 : 0) + (selectedBrands.size > 0 ? 1 : 0) + (priceMin !== null || priceMax !== null ? 1 : 0);

  const filterPanel = (
    <div className="space-y-5">
      <section>
        <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400 mb-2">{t("filter.platform")}</h3>
        <PlatformPills selected={selectedPlatform} onSelect={selectPlatform} layoutId="sheet-platform" platforms={ALL_PLATFORM_KEYS.filter(p => enabledStores.has(p))} />
      </section>
      <section>
        <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400 mb-2">{t("filter.sort")}</h3>
        <div className="flex gap-2 flex-wrap">
          {[{ k: "last_updated", l: t("sort.newest") }, { k: "price", l: t("sort.cheapest") }, { k: "discount", l: t("sort.discount") }].map((s) => (
            <motion.button key={s.k} onClick={() => selectSort(s.k)} whileTap={{ scale: 0.95 }}
              className={`relative px-3 py-1.5 rounded-full text-sm font-medium transition ${selectedSort === s.k ? "text-white" : "bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-200 border border-gray-200 dark:border-gray-700"}`}>
              {selectedSort === s.k && <motion.span layoutId="sheet-sort" className="absolute inset-0 bg-gradient-to-r from-purple-500 to-purple-600 rounded-full shadow-sm" transition={{ type: "spring", stiffness: 500, damping: 35 }} />}
              <span className="relative z-10">{s.l}</span>
            </motion.button>
          ))}
        </div>
      </section>
      <section>
        <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400 mb-2">{t("filter.priceRange")}</h3>
        <div className="flex gap-2 items-center">
          <input type="number" value={priceMin ?? ""} placeholder="Min" onChange={(e) => setPriceMin(e.target.value ? parseFloat(e.target.value) : null)} className="w-24 px-3 py-1.5 rounded-lg bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 text-sm" />
          <span className="text-gray-400">—</span>
          <input type="number" value={priceMax ?? ""} placeholder="Max" onChange={(e) => setPriceMax(e.target.value ? parseFloat(e.target.value) : null)} className="w-24 px-3 py-1.5 rounded-lg bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 text-sm" />
          <span className="text-xs text-gray-400">TL</span>
        </div>
        {priceBounds.max > 0 && (
          <div className="text-[10px] text-gray-400 mt-1">Mevcut aralık: {priceBounds.min} - {priceBounds.max} TL</div>
        )}
      </section>
      <section>
        <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400 mb-2">{t("filter.brand")} ({selectedBrands.size > 0 ? `${selectedBrands.size} seçili` : "tümü"})</h3>
        <div className="flex gap-1.5 flex-wrap max-h-40 overflow-y-auto">
          {allBrands.length === 0 ? (
            <span className="text-xs text-gray-400">—</span>
          ) : allBrands.map(([brand, count]) => {
            const sel = selectedBrands.has(brand);
            return (
              <button key={brand} onClick={() => {
                const next = new Set(selectedBrands);
                if (sel) next.delete(brand); else next.add(brand);
                setSelectedBrands(next);
              }}
                className={`px-2 py-1 rounded-md text-xs font-medium transition ${sel ? "bg-blue-500 text-white" : "bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-300 border border-gray-200 dark:border-gray-700"}`}>
                {brand} <span className="opacity-60">{count}</span>
              </button>
            );
          })}
        </div>
      </section>
      <section>
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">{t("filter.boycott")}</h3>
          <button onClick={async () => {
            const tt = toast.loading("...");
            await refreshBoycottList(true);
            const meta = getBoycottMeta();
            setBoycottMeta(meta);
            toast.success(`${meta.count} brand · ${meta.version}`, { id: tt });
          }} className="text-[10px] font-semibold text-blue-600 dark:text-blue-400 hover:underline">{t("filter.refresh")}</button>
        </div>
        <div className="inline-flex gap-1 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-full p-0.5">
          {BOYCOTT_MODES.map((m) => (
            <button key={m.key} onClick={() => setBoycottMode(m.key)}
              className={`relative px-3 py-1 rounded-full text-xs font-medium transition ${boycottMode === m.key ? "text-white" : "text-gray-600 dark:text-gray-300"}`}>
              {boycottMode === m.key && <motion.span layoutId="sheet-boycott" className="absolute inset-0 bg-gradient-to-r from-rose-500 to-red-600 rounded-full shadow-sm" transition={{ type: "spring", stiffness: 500, damping: 35 }} />}
              <span className="relative z-10 flex items-center gap-1"><span aria-hidden>{m.icon}</span><span>{t(m.tKey)}</span></span>
            </button>
          ))}
        </div>
        <p className="mt-2 text-[10px] text-gray-400 dark:text-gray-500">{boycottMeta.count} · {boycottMeta.version || "?"}</p>
      </section>
      <section className="flex gap-2 flex-wrap">
        <button onClick={() => setFavoritesOnly(!favoritesOnly)} className={`px-3 py-1.5 rounded-lg text-sm font-medium ${favoritesOnly ? "bg-rose-500 text-white" : "bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700"}`}>
          {favoritesOnly ? "★" : "☆"} {t("favorites.title")} ({favorites.size})
        </button>
        <button onClick={exportCsv} className="px-3 py-1.5 rounded-lg text-sm font-medium bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700">📤 {t("common.export")}</button>
        <button onClick={shareUrl} className="px-3 py-1.5 rounded-lg text-sm font-medium bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700">🔗 {t("common.share")}</button>
        {activeFilterCount > 0 && (
          <button onClick={clearAllFilters} className="px-3 py-1.5 rounded-lg text-sm font-medium bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-200">✕ {t("filter.clearAll")}</button>
        )}
      </section>
    </div>
  );

  const categoryPanel = (
    <div className="space-y-3">
      {/* Arama */}
      <div className="relative">
        <input
          type="text"
          value={categoryQuery}
          onChange={(e) => setCategoryQuery(e.target.value)}
          placeholder="Kategori ara…"
          className="w-full pl-8 pr-7 py-1.5 text-sm bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-orange-500/40 focus:border-orange-400"
        />
        <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-xs text-gray-400">🔍</span>
        {categoryQuery && (
          <button
            type="button"
            onClick={() => setCategoryQuery("")}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 text-xs"
            aria-label="Aramayı temizle"
          >
            ✕
          </button>
        )}
      </div>

      {/* Tümü + Toplam */}
      <button
        onClick={() => selectCategory("")}
        className={`flex items-center gap-2 w-full px-3 py-2 text-sm rounded-lg transition-all ${
          selectedCategory === ""
            ? "bg-gradient-to-r from-orange-500 to-red-500 text-white shadow-md shadow-orange-500/20"
            : "bg-gray-50 dark:bg-gray-800 text-gray-700 dark:text-gray-200 hover:bg-orange-50 dark:hover:bg-orange-900/20"
        }`}
      >
        <span>🗂️</span>
        <span className="flex-1 text-left font-semibold">Tümü</span>
        {categoryTotal > 0 && (
          <span
            className={`text-[10px] font-semibold px-1.5 py-0.5 rounded-full ${
              selectedCategory === "" ? "bg-white/25 text-white" : "bg-gray-200 dark:bg-gray-700 text-gray-600 dark:text-gray-300"
            }`}
          >
            {categoryTotal >= 1000 ? `${(categoryTotal / 1000).toFixed(1)}k` : categoryTotal}
          </span>
        )}
      </button>

      {/* Ağaç */}
      <div>
        {categoryTree ? (
          Object.entries(categoryTree).map(([key, value]) => (
            <SidebarItem
              key={key}
              name={key}
              data={value}
              onSelect={selectCategory}
              selected={selectedCategory}
              counts={categoryCounts}
              query={categoryQuery}
            />
          ))
        ) : (
          <div className="space-y-2">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="h-4 bg-gray-100 dark:bg-gray-800 rounded animate-pulse" style={{ width: `${60 + i * 8}%` }} />
            ))}
          </div>
        )}
      </div>
    </div>
  );

  if (maintenanceMsg) {
    return (
      <main className="min-h-screen flex items-center justify-center bg-gradient-to-b from-gray-50 to-gray-100 dark:from-gray-950 dark:to-gray-900 p-6">
        <div className="text-center max-w-md bg-white dark:bg-gray-900 p-8 rounded-2xl shadow-xl border border-gray-200 dark:border-gray-800">
          <div className="text-6xl mb-4">🚧</div>
          <h1 className="text-2xl font-bold mb-2 bg-gradient-to-r from-orange-500 to-red-500 bg-clip-text text-transparent">{brandText.logo}</h1>
          <p className="text-gray-600 dark:text-gray-300">{maintenanceMsg}</p>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-gradient-to-b from-gray-50 to-gray-100 dark:from-gray-950 dark:to-gray-900 text-gray-900 dark:text-gray-100 transition-colors pb-16">
      <header className={`sticky top-0 z-30 transition-all duration-300 ${scrolled ? "bg-white/85 dark:bg-gray-950/85 backdrop-blur-md shadow-sm border-b border-gray-200 dark:border-gray-800" : "bg-transparent"}`}>
        <div className="max-w-[1400px] mx-auto px-3 md:px-6 py-3 flex items-center gap-2">
          <h1 className="text-base md:text-xl font-bold bg-gradient-to-r from-orange-500 to-red-500 bg-clip-text text-transparent truncate">
            {brandText.logo}
          </h1>

          <div className="flex-1 hidden md:flex max-w-md mx-2 gap-2">
            <input type="search" value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} placeholder={t("filter.search")}
              className="flex-1 px-4 py-1.5 rounded-full bg-white/80 dark:bg-gray-800/80 border border-gray-200 dark:border-gray-700 text-sm placeholder:text-gray-400 focus:outline-none focus:border-blue-500" />
            <VoiceSearch onResult={(text) => setSearchQuery(text)} locale={locale === "en" ? "en-US" : "tr-TR"} />
          </div>

          <button onClick={() => setFilterOpen(true)} className="md:hidden flex items-center gap-1.5 ml-1 px-2.5 py-1 rounded-full bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 text-xs text-gray-700 dark:text-gray-200 max-w-[140px] relative">
            <span className="truncate">{PLATFORM_LABELS[selectedPlatform]}</span>
            {activeFilterCount > 0 && <span className="absolute -top-1 -right-1 bg-blue-500 text-white rounded-full text-[9px] w-4 h-4 flex items-center justify-center">{activeFilterCount}</span>}
            <span className="text-gray-400">▾</span>
          </button>

          {totalDeals > 0 && (
            <span className="ml-auto md:ml-2 text-xs md:text-sm font-bold text-orange-600 dark:text-orange-400 bg-orange-50 dark:bg-orange-900/30 border border-orange-200 dark:border-orange-700/50 px-2 md:px-3 py-0.5 md:py-1 rounded-full whitespace-nowrap">
              {visibleDeals.length}
              {hiddenBoycottCount > 0 && <span className="text-rose-600 dark:text-rose-400">/{deals.length}</span>}
            </span>
          )}

          <button onClick={() => setCategoryOpen(true)} className="md:hidden w-9 h-9 rounded-full bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 flex items-center justify-center text-gray-600 dark:text-gray-300" aria-label="Categories">☰</button>

          <motion.button onClick={scrapeAllCategories} disabled={manualScraping}
            whileHover={{ scale: manualScraping ? 1 : 1.04 }} whileTap={{ scale: 0.96 }}
            className="px-3 md:px-4 py-1.5 md:py-2 rounded-lg text-xs md:text-sm font-semibold text-white bg-gradient-to-r from-green-500 to-emerald-600 hover:shadow-lg shadow-md disabled:opacity-50 disabled:cursor-not-allowed transition-shadow whitespace-nowrap">
            {manualScraping ? (
              <span className="flex items-center gap-1.5"><span className="inline-block w-2 h-2 rounded-full bg-white/80 animate-pulse" /><span className="hidden sm:inline">{t("header.scanning")}</span></span>
            ) : (
              <>
                <span className="md:hidden">{t("header.scan")}</span>
                <span className="hidden md:inline">{selectedPlatform === "hepsi" ? t("header.scanAll") : `${PLATFORM_LABELS[selectedPlatform]} ${t("header.scan").toLowerCase()}`}</span>
              </>
            )}
          </motion.button>

          <LanguageToggle />
          <ThemeToggle />
        </div>

        <div className="md:hidden max-w-[1400px] mx-auto px-3 pb-2 flex gap-2">
          <input type="search" value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} placeholder={t("filter.search")}
            className="flex-1 px-4 py-1.5 rounded-full bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 text-sm placeholder:text-gray-400 focus:outline-none focus:border-blue-500" />
          <VoiceSearch onResult={(text) => setSearchQuery(text)} locale={locale === "en" ? "en-US" : "tr-TR"} />
        </div>

        <div className="hidden md:block max-w-[1400px] mx-auto px-6 pb-3">
          <div className="flex items-center gap-3 flex-wrap">
            <div className="flex-1 min-w-0">
              <PlatformPills selected={selectedPlatform} onSelect={selectPlatform} layoutId="desk-platform" platforms={ALL_PLATFORM_KEYS.filter(p => enabledStores.has(p))} />
            </div>
            <button onClick={() => setFilterOpen(true)} className="relative px-3 py-1.5 rounded-full text-sm font-medium bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700">
              ⚙️ {t("filter.title")}
              {activeFilterCount > 0 && <span className="absolute -top-1 -right-1 bg-blue-500 text-white rounded-full text-[10px] w-4 h-4 flex items-center justify-center">{activeFilterCount}</span>}
            </button>
          </div>
        </div>
      </header>

      <div className="max-w-[1400px] mx-auto px-3 md:px-6 pt-4 md:pt-6 flex gap-6">
        <aside className="hidden md:block w-60 shrink-0 sticky top-44 self-start h-[calc(100vh-12rem)] overflow-y-auto bg-white dark:bg-gray-900 p-4 rounded-xl shadow-sm border border-gray-100 dark:border-gray-800">
          <h2 className="font-bold text-sm uppercase tracking-wider text-gray-500 dark:text-gray-400 mb-3">{t("categories.title")}</h2>
          {categoryPanel}
        </aside>

        <div className="flex-1 min-w-0">
          <AnimatePresence mode="wait">
            {loading ? (
              <motion.div key="skeleton" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}><DealGridSkeleton count={9} /></motion.div>
            ) : visibleDeals.length === 0 ? (
              <motion.div key="empty" initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className="text-center py-16 md:py-20 bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-100 dark:border-gray-800">
                <div className="text-5xl md:text-6xl mb-4">🔍</div>
                <h3 className="text-lg md:text-xl text-gray-700 dark:text-gray-200 font-semibold mb-2">{t("empty.title")}</h3>
                <p className="text-gray-400 dark:text-gray-500 text-sm">{t("empty.desc")}</p>
                {activeFilterCount > 0 && (
                  <button onClick={clearAllFilters} className="mt-4 px-4 py-2 rounded-lg bg-blue-500 text-white text-sm font-medium">{t("filter.clearAll")}</button>
                )}
              </motion.div>
            ) : (
              <motion.div key={`grid-${selectedCategory}-${selectedPlatform}-${selectedSort}-${boycottMode}-${searchQuery}-${favoritesOnly}-${[...selectedBrands].join()}-${priceMin}-${priceMax}`} className="grid grid-cols-2 lg:grid-cols-3 gap-3 md:gap-5">
                {visibleDeals.map((deal, idx) => {
                  const discount = deal.discount_percentage || 0;
                  const hotDeal = discount >= 50;
                  const boycottBrand = isBoycotted(deal.title);
                  const showBoycottBadge = boycottBrand && boycottMode !== "show";
                  const isFav = favorites.has(deal.link || "");
                  const trend = computeTrend(deal.price_history, deal.price);

                  return (
                    <motion.div key={`${deal.link}-${idx}`} custom={idx} variants={cardVariants} initial="hidden" animate="visible"
                      whileHover={{ y: -4, transition: { duration: 0.2 } }}
                      className={`relative bg-white dark:bg-gray-900 rounded-xl shadow-sm border overflow-hidden hover:shadow-xl transition-shadow group flex flex-col h-full ${showBoycottBadge ? "border-rose-300 dark:border-rose-700/50 ring-1 ring-rose-200 dark:ring-rose-800/40" : "border-gray-100 dark:border-gray-800"}`}>
                      {showBoycottBadge && (
                        <div className="absolute top-2 left-2 z-10 bg-rose-500 text-white text-[9px] md:text-[10px] font-bold px-1.5 md:px-2 py-0.5 md:py-1 rounded-md shadow-md flex items-center gap-0.5">
                          🚫 <span className="capitalize hidden sm:inline">{boycottBrand}</span>
                        </div>
                      )}
                      <div className="absolute top-2 right-2 z-20 flex flex-col gap-1.5" style={{ marginTop: discount > 0 ? "2rem" : 0 }}>
                        <button onClick={(e) => { e.preventDefault(); e.stopPropagation(); handleToggleFavorite(deal.link || ""); }}
                          className="w-7 h-7 md:w-8 md:h-8 rounded-full bg-white/90 dark:bg-gray-800/90 backdrop-blur-sm flex items-center justify-center hover:scale-110 transition-transform shadow-sm"
                          title={isFav ? t("favorites.remove") : t("favorites.add")}>
                          <span className={isFav ? "text-rose-500" : "text-gray-400 dark:text-gray-500"}>{isFav ? "♥" : "♡"}</span>
                        </button>
                        <AlarmButton link={deal.link || ""} title={deal.title} currentPriceText={deal.price} />
                        <AiSummary deal={deal} />
                      </div>
                      <a href={deal.link || "#"} target="_blank" rel="noreferrer" className="flex-grow flex flex-col">
                        <div className="aspect-square md:h-48 md:aspect-auto bg-white dark:bg-gray-800/40 relative p-2 md:p-4 flex items-center justify-center border-b border-gray-100 dark:border-gray-800 overflow-hidden">
                          {discount > 0 && (
                            <span className={`absolute top-1.5 right-1.5 md:top-2 md:right-2 z-10 font-bold px-1.5 md:px-2 py-0.5 md:py-1 rounded-md text-[10px] md:text-sm text-white shadow-md ${hotDeal ? "bg-gradient-to-r from-red-500 to-orange-500 animate-pulse" : "bg-red-600"}`}>
                              %{discount}
                            </span>
                          )}
                          {trend !== "flat" && (
                            <span className={`absolute bottom-1.5 left-1.5 md:bottom-2 md:left-2 z-10 px-1.5 py-0.5 rounded text-[10px] md:text-xs font-bold ${trend === "down" ? "bg-green-100 dark:bg-green-900/50 text-green-700 dark:text-green-300" : "bg-amber-100 dark:bg-amber-900/50 text-amber-700 dark:text-amber-300"}`} title={trend === "down" ? t("trend.down") : t("trend.up")}>
                              {trend === "down" ? "↓" : "↑"}
                            </span>
                          )}
                          {deal.image ? (
                            <div className="relative w-full h-full">
                              <Image src={deal.image} alt={deal.title} fill sizes="(max-width: 768px) 50vw, (max-width: 1280px) 33vw, 25vw" className="object-contain group-hover:scale-105 transition-transform duration-300" unoptimized />
                            </div>
                          ) : (<div className="text-gray-300 dark:text-gray-600 text-xs">{t("deal.noImage")}</div>)}
                          {deal.price_history && deal.price_history.length > 1 && (
                            <div className="absolute left-2 right-2 bottom-2 bg-white/95 dark:bg-gray-900/95 backdrop-blur-sm rounded-lg p-2 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none shadow-lg border border-gray-200 dark:border-gray-700 hidden md:block">
                              <PriceHistoryChart history={deal.price_history} />
                            </div>
                          )}
                        </div>
                        <div className="p-2.5 md:p-4 flex flex-col flex-grow justify-between">
                          <h3 className="text-gray-800 dark:text-gray-100 font-medium text-xs md:text-sm line-clamp-2 md:line-clamp-3 group-hover:text-orange-500 dark:group-hover:text-orange-400 transition mb-1.5 md:mb-2">{deal.title}</h3>
                          {deal.price && <div className="text-base md:text-xl text-gray-900 dark:text-white font-bold mb-1 md:mb-2">{deal.price.replace("Fırsatın Fiyatı:", "").trim()}</div>}
                          {deal.last_updated && <div className="text-[9px] md:text-[10px] text-gray-400 dark:text-gray-500 mb-2 hidden sm:inline-block bg-gray-50 dark:bg-gray-800 px-1.5 md:px-2 py-0.5 md:py-1 rounded w-fit">{formatTimestamp(deal.last_updated, locale)}</div>}
                          {deal.deal_score !== undefined && deal.deal_score > 0 && (
                            <div className="mb-1.5 md:mb-2 text-sm hidden sm:block">
                              <div className="flex justify-between items-center mb-1">
                                <span className="text-gray-600 dark:text-gray-400 text-[10px] md:text-xs">{t("deal.score")}</span>
                                <span className="font-bold text-orange-600 dark:text-orange-400 text-[10px] md:text-xs">{Math.round(deal.deal_score)}/100</span>
                              </div>
                              <div className="w-full bg-gray-100 dark:bg-gray-800 rounded-full h-1 md:h-1.5 overflow-hidden">
                                <motion.div className="bg-gradient-to-r from-orange-400 to-red-500 h-full rounded-full" initial={{ width: 0 }} animate={{ width: `${deal.deal_score}%` }} transition={{ duration: 0.8, ease: "easeOut", delay: Math.min(idx, 12) * 0.03 }} />
                              </div>
                            </div>
                          )}
                          <div className="flex justify-between items-center mt-auto pt-1.5 md:pt-2">
                            <span className="text-[10px] md:text-xs text-gray-500 dark:text-gray-400 truncate">{PLATFORM_LABELS[(deal.platform as PlatformKey) || "hepsi"] || deal.platform}</span>
                            <span className="text-orange-600 dark:text-orange-400 bg-orange-50 dark:bg-orange-900/30 border border-orange-100 dark:border-orange-700/50 px-1.5 md:px-2 py-0.5 md:py-1 rounded text-[9px] md:text-xs font-bold">{t("deal.deal")}</span>
                          </div>
                        </div>
                      </a>
                    </motion.div>
                  );
                })}
              </motion.div>
            )}
          </AnimatePresence>

          {loadingMore && <div className="mt-6"><DealGridSkeleton count={3} /></div>}
        </div>
      </div>

      <button onClick={() => setFilterOpen(true)}
        className="md:hidden fixed bottom-5 right-5 z-30 w-14 h-14 rounded-full bg-gradient-to-br from-blue-500 to-blue-600 text-white shadow-lg flex items-center justify-center hover:scale-105 active:scale-95 transition-transform">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          <line x1="4" y1="6" x2="20" y2="6" /><line x1="7" y1="12" x2="17" y2="12" /><line x1="10" y1="18" x2="14" y2="18" />
        </svg>
        {activeFilterCount > 0 && <span className="absolute -top-1 -right-1 bg-rose-500 text-white text-xs rounded-full w-5 h-5 flex items-center justify-center font-bold">{activeFilterCount}</span>}
      </button>

      <FilterSheet open={filterOpen} onClose={() => setFilterOpen(false)} title={t("filter.title")}>{filterPanel}</FilterSheet>
      <FilterSheet open={categoryOpen} onClose={() => setCategoryOpen(false)} title={t("categories.title")}>{categoryPanel}</FilterSheet>
    </main>
  );
}
