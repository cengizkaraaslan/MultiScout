const KEY = "multiscout_favorites";

export function getFavorites(): Set<string> {
  if (typeof window === "undefined") return new Set();
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return new Set();
    const arr = JSON.parse(raw);
    return new Set(Array.isArray(arr) ? arr : []);
  } catch {
    return new Set();
  }
}

export function setFavorites(s: Set<string>) {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(KEY, JSON.stringify([...s]));
  } catch {
    /* quota */
  }
}

export function toggleFavorite(link: string): Set<string> {
  const s = getFavorites();
  if (s.has(link)) s.delete(link);
  else s.add(link);
  setFavorites(s);
  return s;
}
