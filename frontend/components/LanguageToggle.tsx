"use client";

import { useI18n } from "../lib/i18n";

export default function LanguageToggle() {
  const { locale, setLocale } = useI18n();
  return (
    <button
      onClick={() => setLocale(locale === "tr" ? "en" : "tr")}
      className="w-10 h-10 rounded-full bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 shadow-sm hover:shadow-md transition flex items-center justify-center text-xs font-bold text-gray-700 dark:text-gray-200"
      aria-label="Language"
      title={locale === "tr" ? "Switch to English" : "Türkçe'ye geç"}
    >
      {locale === "tr" ? "EN" : "TR"}
    </button>
  );
}
