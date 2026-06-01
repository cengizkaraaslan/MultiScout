"use client";

import { useEffect, useState, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";

interface Props {
  onResult: (text: string) => void;
  locale?: string;
}

type SR = {
  start: () => void;
  stop: () => void;
  abort: () => void;
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onresult: ((ev: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null;
  onerror: ((ev: { error: string }) => void) | null;
  onend: (() => void) | null;
};

declare global {
  interface Window {
    SpeechRecognition?: new () => SR;
    webkitSpeechRecognition?: new () => SR;
  }
}

export default function VoiceSearch({ onResult, locale = "tr-TR" }: Props) {
  const [supported, setSupported] = useState(false);
  const [listening, setListening] = useState(false);
  const [interim, setInterim] = useState("");
  const recRef = useRef<SR | null>(null);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const SRClass = window.SpeechRecognition || window.webkitSpeechRecognition;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (SRClass) setSupported(true);
  }, []);

  const stop = () => {
    if (recRef.current) {
      try { recRef.current.stop(); } catch { /* ignore */ }
      recRef.current = null;
    }
    setListening(false);
    setInterim("");
  };

  const start = () => {
    if (typeof window === "undefined") return;
    const SRClass = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SRClass) return;
    const rec = new SRClass();
    rec.continuous = false;
    rec.interimResults = true;
    rec.lang = locale;
    rec.onresult = (ev) => {
      let final = "";
      let inter = "";
      const r = ev.results;
      for (let i = 0; i < r.length; i++) {
        const alt = r[i];
        const transcript = alt && alt[0] ? alt[0].transcript : "";
        // SpeechRecognition results are objects with isFinal flag too, but we
        // use simple last-wins approach
        if (i === r.length - 1) inter = transcript;
        else final += transcript;
      }
      const result = (final + inter).trim();
      setInterim(result);
      if (final || (r.length > 0 && result.length > 0)) {
        onResult(result);
      }
    };
    rec.onerror = () => stop();
    rec.onend = () => stop();
    recRef.current = rec;
    setListening(true);
    setInterim("");
    try { rec.start(); } catch { stop(); }
  };

  if (!supported) return null;

  return (
    <button
      onClick={listening ? stop : start}
      title={listening ? "Dinleme bitti" : "Sesli ara"}
      aria-label="Sesli arama"
      className={`relative w-9 h-9 shrink-0 rounded-full flex items-center justify-center transition shadow-sm ${
        listening
          ? "bg-gradient-to-br from-rose-500 to-red-600 text-white"
          : "bg-white dark:bg-gray-800 text-gray-500 dark:text-gray-300 border border-gray-200 dark:border-gray-700 hover:border-blue-400"
      }`}
    >
      {listening && (
        <motion.span
          className="absolute inset-0 rounded-full border-2 border-rose-400"
          animate={{ scale: [1, 1.5, 1], opacity: [0.7, 0, 0.7] }}
          transition={{ duration: 1.5, repeat: Infinity }}
        />
      )}
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
        <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
        <line x1="12" y1="19" x2="12" y2="23"/>
        <line x1="8" y1="23" x2="16" y2="23"/>
      </svg>
      <AnimatePresence>
        {listening && interim && (
          <motion.div
            initial={{ opacity: 0, y: -5 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="absolute top-11 right-0 z-30 bg-white dark:bg-gray-900 text-xs text-gray-700 dark:text-gray-200 border border-gray-200 dark:border-gray-700 rounded-lg px-3 py-1.5 shadow-lg whitespace-nowrap max-w-[200px] truncate"
          >
            🎤 {interim}
          </motion.div>
        )}
      </AnimatePresence>
    </button>
  );
}
