"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

type BeforeInstallPromptEvent = Event & {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
};

const DISMISS_KEY = "ms_pwa_install_dismissed_at";
const DISMISS_DAYS = 14;

function isStandalone(): boolean {
  if (typeof window === "undefined") return false;
  return (
    window.matchMedia?.("(display-mode: standalone)").matches ||
    // iOS Safari
    (window.navigator as unknown as { standalone?: boolean }).standalone === true
  );
}

function isIOS(): boolean {
  if (typeof navigator === "undefined") return false;
  const ua = navigator.userAgent || "";
  return /iPhone|iPad|iPod/i.test(ua) && !/CriOS|FxiOS/.test(ua);
}

function wasRecentlyDismissed(): boolean {
  try {
    const v = localStorage.getItem(DISMISS_KEY);
    if (!v) return false;
    const dismissedAt = parseInt(v, 10);
    return Date.now() - dismissedAt < DISMISS_DAYS * 24 * 60 * 60 * 1000;
  } catch {
    return false;
  }
}

export default function InstallButton() {
  const [deferred, setDeferred] = useState<BeforeInstallPromptEvent | null>(null);
  const [showBanner, setShowBanner] = useState(false);
  const [iosHint, setIosHint] = useState(false);

  useEffect(() => {
    if (isStandalone()) return;
    if (wasRecentlyDismissed()) return;

    // Android / Desktop Chrome
    const onPrompt = (e: Event) => {
      e.preventDefault();
      setDeferred(e as BeforeInstallPromptEvent);
      setShowBanner(true);
    };
    window.addEventListener("beforeinstallprompt", onPrompt as EventListener);

    // iOS Safari: beforeinstallprompt yoktur, manuel ipucu göster
    if (isIOS()) {
      const t = setTimeout(() => setIosHint(true), 4000);
      return () => {
        clearTimeout(t);
        window.removeEventListener("beforeinstallprompt", onPrompt as EventListener);
      };
    }
    return () => window.removeEventListener("beforeinstallprompt", onPrompt as EventListener);
  }, []);

  useEffect(() => {
    const onInstalled = () => {
      setShowBanner(false);
      setIosHint(false);
      setDeferred(null);
    };
    window.addEventListener("appinstalled", onInstalled);
    return () => window.removeEventListener("appinstalled", onInstalled);
  }, []);

  const dismiss = () => {
    try { localStorage.setItem(DISMISS_KEY, String(Date.now())); } catch {}
    setShowBanner(false);
    setIosHint(false);
  };

  const install = async () => {
    if (!deferred) return;
    await deferred.prompt();
    const choice = await deferred.userChoice;
    if (choice.outcome === "dismissed") dismiss();
    else setShowBanner(false);
    setDeferred(null);
  };

  if (!showBanner && !iosHint) return null;

  return (
    <AnimatePresence>
      <motion.div
        key="install-banner"
        initial={{ y: 80, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        exit={{ y: 80, opacity: 0 }}
        transition={{ type: "spring", stiffness: 260, damping: 24 }}
        className="fixed bottom-4 inset-x-3 md:inset-x-auto md:right-6 md:bottom-6 z-50 max-w-md mx-auto"
      >
        <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-2xl shadow-2xl shadow-black/10 p-4 flex items-start gap-3">
          <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-orange-500 to-red-500 flex items-center justify-center text-white font-bold text-xl shrink-0">M</div>
          <div className="flex-1 min-w-0">
            <p className="font-semibold text-sm text-gray-900 dark:text-gray-100">
              MultiScout&apos;u telefonuna ekle
            </p>
            <p className="text-xs text-gray-600 dark:text-gray-400 mt-0.5">
              {showBanner
                ? "Ana ekrana widget gibi yerleşir, tek dokunuşla indirimleri açar."
                : "Safari’de paylaş ↑ → “Ana Ekrana Ekle” ile uygulama gibi kullan."}
            </p>
            <div className="flex gap-2 mt-3">
              {showBanner && (
                <button
                  onClick={install}
                  className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-gradient-to-r from-orange-500 to-red-500 text-white shadow hover:opacity-95"
                >
                  Ana ekrana ekle
                </button>
              )}
              <button
                onClick={dismiss}
                className="px-3 py-1.5 rounded-lg text-xs font-medium bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-200 hover:bg-gray-200 dark:hover:bg-gray-700"
              >
                {showBanner ? "Şimdi değil" : "Tamam"}
              </button>
            </div>
          </div>
        </div>
      </motion.div>
    </AnimatePresence>
  );
}
