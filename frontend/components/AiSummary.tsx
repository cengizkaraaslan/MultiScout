"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { getAiSummary } from "../lib/ai";

interface Props {
  deal: {
    link?: string;
    title?: string;
    price?: string;
    discount_percentage?: number;
    platform?: string;
    price_history?: unknown[];
  };
}

export default function AiSummary({ deal }: Props) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [summary, setSummary] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchSummary = async () => {
    if (summary || loading) {
      setOpen(!open);
      return;
    }
    setLoading(true);
    setError(null);
    const res = await getAiSummary(deal);
    setLoading(false);
    if (res.ok && res.summary) {
      setSummary(res.summary);
      setOpen(true);
    } else {
      setError(res.error || "Hata");
      setOpen(true);
    }
  };

  return (
    <div className="relative">
      <button
        onClick={(e) => { e.preventDefault(); e.stopPropagation(); fetchSummary(); }}
        className="w-7 h-7 md:w-8 md:h-8 rounded-full bg-gradient-to-br from-purple-500 to-pink-500 text-white flex items-center justify-center hover:scale-110 transition-transform shadow-sm text-xs font-bold"
        title="AI yorumu"
      >
        ✨
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 5 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95 }}
            onClick={(e) => { e.preventDefault(); e.stopPropagation(); }}
            className="absolute top-9 right-0 z-30 bg-white dark:bg-gray-900 rounded-lg shadow-xl border border-purple-200 dark:border-purple-700/50 p-3 w-64"
          >
            <div className="flex items-center gap-1.5 mb-2">
              <span className="text-purple-500">✨</span>
              <span className="text-xs font-bold text-gray-700 dark:text-gray-200">AI Analiz</span>
              <button onClick={() => setOpen(false)} className="ml-auto text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 text-sm">×</button>
            </div>
            {loading ? (
              <div className="text-xs text-gray-500 dark:text-gray-400 py-2 flex items-center gap-2">
                <span className="inline-block w-2 h-2 rounded-full bg-purple-500 animate-pulse" />
                Analiz ediliyor...
              </div>
            ) : error ? (
              <div className="text-xs text-rose-500">{error}</div>
            ) : (
              <p className="text-xs text-gray-700 dark:text-gray-200 leading-relaxed">{summary}</p>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
