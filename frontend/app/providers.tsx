"use client";

import { ThemeProvider } from "next-themes";
import { Toaster } from "sonner";
import { I18nProvider } from "../lib/i18n";

export default function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
      <I18nProvider>
        {children}
        <Toaster richColors position="top-right" closeButton />
      </I18nProvider>
    </ThemeProvider>
  );
}
