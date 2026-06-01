"use client";

import { useEffect } from "react";
import { AnimatePresence, motion } from "framer-motion";

interface FilterSheetProps {
  open: boolean;
  onClose: () => void;
  children: React.ReactNode;
  title?: string;
}

export default function FilterSheet({ open, onClose, children, title = "Filtreler" }: FilterSheetProps) {
  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = prev;
      window.removeEventListener("keydown", onKey);
    };
  }, [open, onClose]);

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            key="backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 bg-black/50 backdrop-blur-sm z-40"
            aria-hidden
          />
          <motion.div
            key="sheet"
            initial={{ y: "100%" }}
            animate={{ y: 0 }}
            exit={{ y: "100%" }}
            transition={{ type: "spring", damping: 32, stiffness: 280 }}
            className="fixed bottom-0 left-0 right-0 z-50 bg-white dark:bg-gray-900 rounded-t-2xl shadow-2xl max-h-[85vh] overflow-y-auto overscroll-contain"
            role="dialog"
            aria-modal
          >
            <div className="sticky top-0 bg-white dark:bg-gray-900 z-10 px-4 pt-3 pb-2 border-b border-gray-100 dark:border-gray-800">
              <button
                onClick={onClose}
                aria-label="Kapat"
                className="w-12 h-1.5 bg-gray-300 dark:bg-gray-700 rounded-full mx-auto mb-3 block cursor-pointer hover:bg-gray-400"
              />
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-bold text-gray-900 dark:text-gray-100">{title}</h2>
                <button
                  onClick={onClose}
                  className="w-9 h-9 rounded-full hover:bg-gray-100 dark:hover:bg-gray-800 flex items-center justify-center text-gray-500 dark:text-gray-400 text-lg"
                  aria-label="Kapat"
                >
                  ✕
                </button>
              </div>
            </div>
            <div className="p-4 pb-10">{children}</div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
