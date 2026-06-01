const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const PASS_KEY = "multiscout_admin_pw";

export function getAdminPassword(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(PASS_KEY);
}

export function setAdminPassword(pw: string) {
  if (typeof window === "undefined") return;
  localStorage.setItem(PASS_KEY, pw);
}

export function clearAdminPassword() {
  if (typeof window === "undefined") return;
  localStorage.removeItem(PASS_KEY);
}

export async function adminLogin(password: string): Promise<boolean> {
  try {
    const res = await fetch(`${API_URL}/api/admin/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password }),
    });
    if (!res.ok) return false;
    const data = await res.json();
    if (data.status === "success") {
      setAdminPassword(password);
      return true;
    }
    return false;
  } catch {
    return false;
  }
}

export async function adminGetSettings(): Promise<Record<string, unknown> | null> {
  const pw = getAdminPassword();
  if (!pw) return null;
  try {
    const res = await fetch(`${API_URL}/api/admin/settings`, {
      headers: { "X-ADMIN-PASSWORD": pw },
    });
    if (!res.ok) return null;
    const data = await res.json();
    return data.data || null;
  } catch {
    return null;
  }
}

export async function adminPatchSection(section: string, payload: Record<string, unknown>): Promise<boolean> {
  const pw = getAdminPassword();
  if (!pw) return false;
  try {
    const res = await fetch(`${API_URL}/api/admin/settings/${section}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", "X-ADMIN-PASSWORD": pw },
      body: JSON.stringify(payload),
    });
    return res.ok;
  } catch {
    return false;
  }
}

export async function getPublicStoresStatus(): Promise<{
  stores: Record<string, boolean>;
  enabled: string[];
  theme: Record<string, string>;
  maintenance: { enabled: boolean; message: string };
} | null> {
  try {
    const res = await fetch(`${API_URL}/api/stores-status`);
    if (!res.ok) return null;
    const data = await res.json();
    return {
      stores: data.stores || {},
      enabled: data.enabled || [],
      theme: data.theme || {},
      maintenance: data.maintenance || { enabled: false, message: "" },
    };
  } catch {
    return null;
  }
}
