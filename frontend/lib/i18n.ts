"use client";

import { createContext, useContext, useEffect, useState, ReactNode, createElement } from "react";

export type Locale = "tr" | "en";

const STORAGE_KEY = "multiscout_locale";

type Dict = Record<string, string>;

const TR: Dict = {
  "app.title": "MultiScout",
  "app.tagline": "Fırsat Takipçisi",
  "header.scan": "Tara",
  "header.scanAll": "Tümünü tara",
  "header.scanning": "Taranıyor...",
  "filter.title": "Filtreler",
  "filter.platform": "Platform",
  "filter.sort": "Sıralama",
  "filter.boycott": "Boykot Ürünleri",
  "filter.brand": "Marka",
  "filter.priceRange": "Fiyat Aralığı",
  "filter.search": "Ürün ara...",
  "filter.refresh": "↻ Güncelle",
  "filter.clearAll": "Tümünü temizle",
  "sort.newest": "Yeni",
  "sort.cheapest": "Ucuzdan",
  "sort.discount": "İndirim",
  "boycott.highlight": "İşaretle",
  "boycott.hide": "Gizle",
  "boycott.show": "Göster",
  "categories.title": "Kategoriler",
  "deal.score": "Skor",
  "deal.deal": "FIRSAT",
  "deal.noImage": "Görsel Yok",
  "deal.viewOn": "Gör",
  "empty.title": "Henüz Fırsat Bulunamadı",
  "empty.desc": "\"Tara\" butonuna tıklayarak fırsatları yükleyin.",
  "loading.products": "Veriler yükleniyor...",
  "loading.more": "Daha fazla ürün yükleniyor...",
  "loading.categories": "Kategoriler yükleniyor...",
  "favorites.title": "Favoriler",
  "favorites.add": "Favorilere ekle",
  "favorites.remove": "Favorilerden çıkar",
  "favorites.empty": "Henüz favori yok",
  "stats.dealsCount": "fırsat",
  "stats.hidden": "gizli",
  "common.close": "Kapat",
  "common.export": "Dışa aktar (CSV)",
  "common.share": "Paylaş",
  "common.copied": "Bağlantı kopyalandı",
  "trend.up": "Yükseliyor",
  "trend.down": "Düşüyor",
  "trend.flat": "Sabit",
  "lang.tr": "Türkçe",
  "lang.en": "English",
};

const EN: Dict = {
  "app.title": "MultiScout",
  "app.tagline": "Deal Tracker",
  "header.scan": "Scan",
  "header.scanAll": "Scan all",
  "header.scanning": "Scanning...",
  "filter.title": "Filters",
  "filter.platform": "Platform",
  "filter.sort": "Sort",
  "filter.boycott": "Boycott Products",
  "filter.brand": "Brand",
  "filter.priceRange": "Price Range",
  "filter.search": "Search products...",
  "filter.refresh": "↻ Refresh",
  "filter.clearAll": "Clear all",
  "sort.newest": "Newest",
  "sort.cheapest": "Cheapest",
  "sort.discount": "Discount",
  "boycott.highlight": "Mark",
  "boycott.hide": "Hide",
  "boycott.show": "Show",
  "categories.title": "Categories",
  "deal.score": "Score",
  "deal.deal": "DEAL",
  "deal.noImage": "No image",
  "deal.viewOn": "View",
  "empty.title": "No Deals Found Yet",
  "empty.desc": "Click \"Scan\" to load deals.",
  "loading.products": "Loading deals...",
  "loading.more": "Loading more...",
  "loading.categories": "Loading categories...",
  "favorites.title": "Favorites",
  "favorites.add": "Add to favorites",
  "favorites.remove": "Remove from favorites",
  "favorites.empty": "No favorites yet",
  "stats.dealsCount": "deals",
  "stats.hidden": "hidden",
  "common.close": "Close",
  "common.export": "Export (CSV)",
  "common.share": "Share",
  "common.copied": "Link copied",
  "trend.up": "Rising",
  "trend.down": "Falling",
  "trend.flat": "Stable",
  "lang.tr": "Türkçe",
  "lang.en": "English",
};

const DICTS: Record<Locale, Dict> = { tr: TR, en: EN };

interface I18nContextValue {
  locale: Locale;
  setLocale: (l: Locale) => void;
  t: (key: string) => string;
}

const I18nContext = createContext<I18nContextValue>({
  locale: "tr",
  setLocale: () => {},
  t: (k) => TR[k] || k,
});

export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>("tr");

  useEffect(() => {
    if (typeof window === "undefined") return;
    const stored = localStorage.getItem(STORAGE_KEY);
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (stored === "tr" || stored === "en") setLocaleState(stored);
  }, []);

  const setLocale = (l: Locale) => {
    setLocaleState(l);
    try {
      localStorage.setItem(STORAGE_KEY, l);
    } catch {
      /* quota */
    }
  };

  const t = (key: string): string => {
    return DICTS[locale][key] ?? DICTS.tr[key] ?? key;
  };

  return createElement(I18nContext.Provider, { value: { locale, setLocale, t } }, children);
}

export function useI18n(): I18nContextValue {
  return useContext(I18nContext);
}
