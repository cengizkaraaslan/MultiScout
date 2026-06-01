// Fiyat alarmı — localStorage + browser Notification API
// {link, targetPrice, title, currentPrice, triggered}

const KEY = "multiscout_price_alarms";

export interface PriceAlarm {
  link: string;
  targetPrice: number;
  title: string;
  lastSeenPrice: number;
  triggered: boolean;
  createdAt: number;
  triggeredAt?: number;
}

export function getAlarms(): PriceAlarm[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

export function saveAlarms(alarms: PriceAlarm[]) {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(KEY, JSON.stringify(alarms));
  } catch {
    /* quota */
  }
}

export function addOrUpdateAlarm(alarm: PriceAlarm) {
  const list = getAlarms();
  const idx = list.findIndex((a) => a.link === alarm.link);
  if (idx >= 0) list[idx] = alarm;
  else list.push(alarm);
  saveAlarms(list);
  return list;
}

export function removeAlarm(link: string) {
  const list = getAlarms().filter((a) => a.link !== link);
  saveAlarms(list);
  return list;
}

export function getAlarm(link: string): PriceAlarm | null {
  return getAlarms().find((a) => a.link === link) || null;
}

export async function requestNotificationPermission(): Promise<boolean> {
  if (typeof window === "undefined" || !("Notification" in window)) return false;
  if (Notification.permission === "granted") return true;
  if (Notification.permission === "denied") return false;
  const perm = await Notification.requestPermission();
  return perm === "granted";
}

export function checkAlarms(deals: Array<{ link?: string; price?: string; title?: string }>): PriceAlarm[] {
  const list = getAlarms();
  if (list.length === 0) return [];
  const newlyTriggered: PriceAlarm[] = [];
  let changed = false;
  for (const deal of deals) {
    if (!deal.link) continue;
    const alarm = list.find((a) => a.link === deal.link);
    if (!alarm || alarm.triggered) continue;
    const price = parsePriceTL(deal.price);
    if (price > 0) {
      alarm.lastSeenPrice = price;
      if (price <= alarm.targetPrice) {
        alarm.triggered = true;
        alarm.triggeredAt = Date.now();
        newlyTriggered.push(alarm);
      }
      changed = true;
    }
  }
  if (changed) saveAlarms(list);
  // Tetikle browser notification
  if (newlyTriggered.length > 0 && typeof window !== "undefined" && "Notification" in window && Notification.permission === "granted") {
    for (const a of newlyTriggered) {
      try {
        new Notification(`🔔 Fiyat alarmı: ${a.title.substring(0, 50)}`, {
          body: `Hedef ${a.targetPrice} TL altına düştü (${a.lastSeenPrice} TL)`,
          icon: "/icon-192.svg",
          tag: `alarm-${a.link}`,
        });
      } catch {
        /* notification may fail in some browsers */
      }
    }
  }
  return newlyTriggered;
}

function parsePriceTL(p: string | undefined | null): number {
  if (!p) return 0;
  const m = p.match(/\d{1,3}(?:\.\d{3})+(?:,\d{2})?|\d+,\d{2}|\d+\.\d{2}|\d+/);
  if (!m) return 0;
  let raw = m[0];
  if (raw.includes(",")) raw = raw.replace(/\./g, "").replace(",", ".");
  return parseFloat(raw) || 0;
}
