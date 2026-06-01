"use client";

import { useEffect } from "react";

export default function ServiceWorkerRegister() {
  useEffect(() => {
    if (typeof window === "undefined") return;
    if (!("serviceWorker" in navigator)) return;

    const register = async () => {
      try {
        const reg = await navigator.serviceWorker.register("/sw.js", { scope: "/" });
        // Yeni SW bekliyorsa, ana sayfayı bir sonraki ziyarette tazele
        if (reg.waiting) reg.waiting.postMessage({ type: "SKIP_WAITING" });
        reg.addEventListener("updatefound", () => {
          const nw = reg.installing;
          if (!nw) return;
          nw.addEventListener("statechange", () => {
            if (nw.state === "installed" && navigator.serviceWorker.controller) {
              // Yeni versiyon hazır — sessizce devral
              nw.postMessage({ type: "SKIP_WAITING" });
            }
          });
        });
      } catch (err) {
        // SW kayıt başarısız (file:// veya HTTP/insecure context) — sessizce devam
        console.warn("[SW] register failed:", err);
      }
    };

    // Sayfa yüklenmesini engelleme — load sonrası kaydet
    if (document.readyState === "complete") register();
    else window.addEventListener("load", register, { once: true });
  }, []);

  return null;
}
