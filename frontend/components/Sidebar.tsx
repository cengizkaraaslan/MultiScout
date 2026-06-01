"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

type CategoryNode = string[] | { [key: string]: CategoryNode };

interface SidebarItemProps {
  name: string;
  data: CategoryNode;
  onSelect: (item: string) => void;
  selected: string;
  depth?: number;
  counts?: Record<string, number>;
  query?: string;
}

const CATEGORY_ICONS: Record<string, string> = {
  // Üst gruplar (backend _CATEGORY_GROUPS ile uyumlu)
  elektronik: "💻",
  "yiyecek & i̇çecek": "🍔",
  "yiyecek & içecek": "🍔",
  yiyecek: "🍔",
  "kitap & hobi": "📚",
  kitap: "📚",
  "oyuncak & bebek": "🧸",
  oyuncak: "🧸",
  "spor & outdoor": "⚽",
  spor: "⚽",
  "moda — kadın": "👗",
  "moda — erkek": "👔",
  "moda — çocuk": "🧒",
  "moda — i̇ç giyim": "🩲",
  "moda — iç giyim": "🩲",
  moda: "👗",
  "ev & yaşam": "🏠",
  ev: "🏠",
  "temizlik & bakım": "🧼",
  "kişisel bakım & kozmetik": "🧴",
  "kişisel bakım": "🧴",
  "saat & aksesuar": "⌚",
  mücevher: "💍",
  "çiçek & hediye": "🌷",
  "ofis & kırtasiye": "📎",
  ayakkabı: "👟",
  ayakkabi: "👟",
  ofis: "📎",
  bebek: "🍼",
  diğer: "📦",
  // Alt slug'lar
  "kisisel-bakim": "🧴",
  notebook: "💻",
  telefon: "📱",
  tv: "📺",
  televizyon: "📺",
  kulaklik: "🎧",
  tablet: "📲",
  "beyaz-esya": "🔌",
  beyazesya: "🔌",
  bilgisayar: "🖥️",
  oyun: "🎮",
  "oyun-konsol": "🕹️",
  kosu: "🏃",
  bisiklet: "🚴",
  kamp: "⛺",
  yoga: "🧘",
  kahve: "☕",
  "kahve-makinesi": "☕",
  "kahve-makineleri": "☕",
  parfum: "💐",
  cicek: "🌷",
  hediye: "🎁",
  hediyelik: "🎁",
  kadin: "👩",
  erkek: "👨",
  cocuk: "🧒",
  "ic-giyim": "🩲",
  pantolon: "👖",
  elbise: "👗",
  "kadin-spor-ayakkabi": "👟",
  "erkek-spor-ayakkabi": "👟",
  "bebek-bezi": "🧷",
  "tencere-seti": "🍲",
  yazici: "🖨️",
  // Market alt kategorileri
  "sut-kahvalti": "🥛",
  "sut-kahvaltilik": "🥛",
  "et-tavuk": "🍗",
  "et-tavuk-balik": "🍗",
  "sebze-meyve": "🥦",
  "meyve-sebze": "🥦",
  "temel-gida": "🌾",
  icecek: "🥤",
  atistirmalik: "🍿",
  temizlik: "🧼",
  "hijyen-bebek": "🍼",
  dondurma: "🍦",
  // Beyaz eşya
  buzdolabi: "❄️",
  "camasir-makinesi": "🌀",
  "bulasik-makinesi": "🍽️",
  firin: "🔥",
  klima: "💨",
  "elektrikli-supurge": "🧹",
  ankastre: "🔧",
  // Kozmetik
  makyaj: "💄",
  ruj: "💋",
  maskara: "👁️",
  oje: "💅",
  sampuan: "🧴",
  // Mücevher / saat
  kolye: "📿",
  yuzuk: "💍",
  kupe: "✨",
  bilezik: "🔗",
  altin: "🥇",
  saat: "⌚",
};

const iconFor = (label: string): string => {
  const key = label.toLowerCase().trim();
  return CATEGORY_ICONS[key] || "🏷️";
};

const SPECIAL_LABELS: Record<string, string> = {
  "kisisel-bakim": "Kişisel Bakım",
  "beyaz-esya": "Beyaz Eşya",
  "oyun-konsol": "Oyun Konsol",
  "kahve-makinesi": "Kahve Makinesi",
  "kahve-makineleri": "Kahve Makineleri",
  "ic-giyim": "İç Giyim",
  "kadin-spor-ayakkabi": "Kadın Spor Ayakkabı",
  "erkek-spor-ayakkabi": "Erkek Spor Ayakkabı",
  "tencere-seti": "Tencere Seti",
  "bebek-bezi": "Bebek Bezi",
  "sut-kahvalti": "Süt & Kahvaltı",
  "sut-kahvaltilik": "Süt & Kahvaltılık",
  "et-tavuk": "Et & Tavuk",
  "et-tavuk-balik": "Et, Tavuk, Balık",
  "sebze-meyve": "Sebze & Meyve",
  "meyve-sebze": "Meyve & Sebze",
  "temel-gida": "Temel Gıda",
  "hijyen-bebek": "Hijyen & Bebek",
  "camasir-makinesi": "Çamaşır Makinesi",
  "bulasik-makinesi": "Bulaşık Makinesi",
  "elektrikli-supurge": "Elektrikli Süpürge",
  "kucuk-ev-aletleri": "Küçük Ev Aletleri",
  "kadin-elbise": "Kadın Elbise",
  "kadin-pantolon": "Kadın Pantolon",
  "kadin-bluz": "Kadın Bluz",
  "kadin-tisort": "Kadın Tişört",
  "kadin-mont": "Kadın Mont",
  "kadin-etek": "Kadın Etek",
  "kadin-ic-giyim": "Kadın İç Giyim",
  "kadin-outlet": "Kadın Outlet",
  "kadin-ayakkabi": "Kadın Ayakkabı",
  "kadin-canta": "Kadın Çanta",
  "erkek-tisort": "Erkek Tişört",
  "erkek-pantolon": "Erkek Pantolon",
  "erkek-gomlek": "Erkek Gömlek",
  "erkek-mont": "Erkek Mont",
  "erkek-sweat": "Erkek Sweat",
  "erkek-sweatshirt": "Erkek Sweatshirt",
  "erkek-ayakkabi": "Erkek Ayakkabı",
  "cocuk-kiyafet": "Çocuk Kıyafet",
  "bebek-kiyafet": "Bebek Kıyafet",
  notebook: "Notebook",
  tv: "TV",
  n11: "N11",
};

const prettyLabel = (label: string): string => {
  const lc = label.toLowerCase();
  if (SPECIAL_LABELS[lc]) return SPECIAL_LABELS[lc];
  return label
    .split("-")
    .map((w) => (w ? w.charAt(0).toUpperCase() + w.slice(1) : ""))
    .join(" ");
};

const fmtCount = (n: number): string => {
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return String(n);
};

// "domates" kategorisini "tomato" arar gibi ara — Türkçe lokalize lower + slug eşit
const matchesQuery = (label: string, query: string): boolean => {
  if (!query) return true;
  const q = query.toLocaleLowerCase("tr");
  return label.toLocaleLowerCase("tr").includes(q) || prettyLabel(label).toLocaleLowerCase("tr").includes(q);
};

// Recursive: subtree içinde query'ye uyan en az 1 leaf var mı?
const subtreeHasMatch = (node: CategoryNode, query: string): boolean => {
  if (!query) return true;
  if (Array.isArray(node)) return node.some((it) => matchesQuery(it, query));
  return Object.entries(node).some(([k, v]) => matchesQuery(k, query) || subtreeHasMatch(v, query));
};

const SidebarItem = ({ name, data, onSelect, selected, depth = 0, counts, query = "" }: SidebarItemProps) => {
  const [isOpen, setIsOpen] = useState(depth === 0);
  const effectiveOpen = isOpen || Boolean(query);

  if (Array.isArray(data)) {
    const items = query ? data.filter((it) => matchesQuery(it, query)) : data;
    if (!items.length) return null;
    return (
      <div className="space-y-0.5">
        {items.map((item) => {
          const active = selected === item;
          const cnt = counts?.[item];
          return (
            <motion.button
              key={item}
              onClick={() => onSelect(item)}
              whileTap={{ scale: 0.97 }}
              className={`group flex items-center gap-2.5 w-full text-left px-3 py-2 text-sm rounded-lg transition-all ${
                active
                  ? "bg-gradient-to-r from-orange-500 to-red-500 text-white shadow-md shadow-orange-500/20"
                  : "text-gray-700 dark:text-gray-300 hover:bg-orange-50 dark:hover:bg-orange-900/20 hover:text-orange-700 dark:hover:text-orange-300"
              }`}
            >
              <span className="text-base shrink-0">{iconFor(item)}</span>
              <span className="truncate font-medium flex-1">{prettyLabel(item)}</span>
              {typeof cnt === "number" && cnt > 0 && (
                <span
                  className={`shrink-0 text-[10px] font-semibold px-1.5 py-0.5 rounded-full ${
                    active
                      ? "bg-white/25 text-white"
                      : "bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-400 group-hover:bg-orange-200 group-hover:text-orange-900 dark:group-hover:bg-orange-800 dark:group-hover:text-orange-100"
                  }`}
                >
                  {fmtCount(cnt)}
                </span>
              )}
            </motion.button>
          );
        })}
      </div>
    );
  }

  if (!subtreeHasMatch(data, query)) return null;

  // Grup toplamı: bu alt-ağaçtaki tüm leaf count'larının toplamı
  const flattenLeaves = (n: CategoryNode): string[] =>
    Array.isArray(n) ? n : Object.values(n).flatMap(flattenLeaves);
  const groupTotal = counts ? flattenLeaves(data).reduce((s, k) => s + (counts[k] || 0), 0) : 0;

  return (
    <div className="mb-1">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center w-full text-left text-xs font-bold text-gray-500 dark:text-gray-400 uppercase tracking-wider px-2 py-1.5 hover:text-gray-700 dark:hover:text-gray-200 transition"
      >
        <motion.span
          animate={{ rotate: effectiveOpen ? 90 : 0 }}
          transition={{ duration: 0.15 }}
          className="mr-1.5 text-[10px]"
        >
          ▶
        </motion.span>
        <span className="flex items-center gap-1.5 flex-1">
          <span>{iconFor(name)}</span>
          <span>{name}</span>
        </span>
        {groupTotal > 0 && (
          <span className="ml-auto text-[10px] font-semibold text-gray-400 dark:text-gray-500 bg-gray-100 dark:bg-gray-800 px-1.5 py-0.5 rounded-full">
            {fmtCount(groupTotal)}
          </span>
        )}
      </button>
      <AnimatePresence initial={false}>
        {effectiveOpen && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="mt-1 ml-2 pl-2 border-l-2 border-orange-200 dark:border-orange-900/40">
              {Object.entries(data).map(([key, value]) => (
                <SidebarItem
                  key={key}
                  name={key}
                  data={value}
                  onSelect={onSelect}
                  selected={selected}
                  depth={depth + 1}
                  counts={counts}
                  query={query}
                />
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default SidebarItem;
