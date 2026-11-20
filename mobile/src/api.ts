import * as SecureStore from "expo-secure-store";

export const API_BASE = "https://9ywu5lapwb.apps.bot-hosting.cloud";
const TOKEN_KEY = "vindora_office_access_token";

let token: string | null = null;
export async function loadToken() {
  token = await SecureStore.getItemAsync(TOKEN_KEY);
  return token;
}
export async function saveToken(value: string) {
  token = value;
  await SecureStore.setItemAsync(TOKEN_KEY, value);
}
export async function clearToken() {
  token = null;
  await SecureStore.deleteItemAsync(TOKEN_KEY);
}
export async function api<T>(path: string, options: { method?: string; body?: unknown } = {}): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(API_BASE + path, {
    method: options.method || "GET", headers,
    ...(options.body !== undefined ? { body: JSON.stringify(options.body) } : {}),
  });
  const data: any = await response.json().catch(() => ({}));
  if (response.status === 401) {
    await clearToken();
    throw new Error("انتهت جلسة الدخول. سجّل الدخول مرة أخرى.");
  }
  if (!response.ok) throw new Error(data.detail || `خطأ في الاتصال (${response.status})`);
  return data as T;
}
