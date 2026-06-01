"use client";
/* eslint-disable react-hooks/purity */

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { toast } from "sonner";
import { getAlarm, addOrUpdateAlarm, removeAlarm, requestNotificationPermission, type PriceAlarm } from "../lib/alarms";

interface Props {
  link: string;
  title: string;
  currentPriceText?: string;
}

function parseTL(s?: string): number {
  if (!s) return 0;
  const m = s.match(/\d{1,3}(?:\.\d{3})+(?:,\d{2})?|\d+,\d{2}|\d+/);
  if (!m) return 0;
  let raw = m[0];
  if (raw.includes(",")) raw = raw.replace(/\./g, "").replace(",", ".");
  return parseFloat(raw) || 0;
}

export default function AlarmButton({ link, title, currentPriceText }: Props) {
  const [open, setOpen] = useState(false);
  const [existing, setExisting] = useState<PriceAlarm | null>(null);
  const [target, setTarget] = useState("");

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setExisting(getAlarm(link));
  }, [link]);

  const current = parseTL(currentPriceText);

  const save = async () => {
    const targetNum = parseFloat(target);
    if (!targetNum || targetNum <= 0) {
      toast.error("Geçerli bir TL değeri gir");
      return;
    }
    await requestNotificationPermission();
    const alarm: PriceAlarm = {
      link,
      targetPrice: targetNum,
      title,
      lastSeenPrice: current,
      triggered: false,
      createdAt: Date.now(),
    };
    addOrUpdateAlarm(alarm);
    setExisting(alarm);
    setOpen(false);
    toast.success(`Alarm kuruldu: ≤ ${targetNum} TL`);
  };

  const remove = () => {
    removeAlarm(link);
    setExisting(null);
    setOpen(false);
    toast.message("Alarm silindi");
  };

  return (
    <div className="relative">
      <button
        onClick={(e) => { e.preventDefault(); e.stopPropagation(); setOpen(!open); setTarget(existing?.targetPrice?.toString() || (current > 0 ? Math.floor(current * 0.8).toString() : "")); }}
        className={`w-7 h-7 md:w-8 md:h-8 rounded-full bg-white/90 dark:bg-gray-800/90 backdrop-blur-sm flex items-center justify-center hover:scale-110 transition-transform shadow-sm ${existing ? "ring-2 ring-amber-400" : ""}`}
        title={existing ? `Alarm: ≤${existing.targetPrice} TL` : "Fiyat alarmı kur"}
      >
        <span className={existing ? "text-amber-500" : "text-gray-400 dark:text-gray-500"}>🔔</span>
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 5 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95 }}
            onClick={(e) => { e.preventDefault(); e.stopPropagation(); }}
            className="absolute top-9 right-0 z-30 bg-white dark:bg-gray-900 rounded-lg shadow-xl border border-gray-200 dark:border-gray-700 p-3 w-56"
          >
            <div className="text-xs text-gray-600 dark:text-gray-400 mb-2">Fiyat ≤ X TL olunca uyar</div>
            <div className="text-[10px] text-gray-400 mb-1">Şu an: {current ? `${current.toFixed(0)} TL` : "—"}</div>
            <input
              type="number"
              value={target}
              onChange={(e) => setTarget(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") save(); }}
              placeholder="hedef fiyat"
              className="w-full px-2 py-1.5 rounded bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 text-sm"
            />
            <div className="flex gap-1.5 mt-2">
              <button onClick={save} className="flex-1 px-2 py-1 rounded bg-blue-500 text-white text-xs font-medium">Kaydet</button>
              {existing && <button onClick={remove} className="px-2 py-1 rounded bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 text-xs">Sil</button>}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
