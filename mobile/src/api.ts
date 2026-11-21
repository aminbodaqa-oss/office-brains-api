import * as SecureStore from "expo-secure-store";

export const API_BASE = "https://9ywu5lapwb.apps.bot-hosting.cloud";
const TOKEN_KEY = "vindora_office_access_token";
const REFRESH_TOKEN_KEY = "vindora_office_refresh_token";
const PUSH_TOKEN_KEY = "vindora_office_push_token";

let token: string | null = null;
let refreshToken: string | null = null;
let refreshPromise: Promise<boolean | null> | null = null;

export async function loadToken() {
  token = await SecureStore.getItemAsync(TOKEN_KEY);
  refreshToken = await SecureStore.getItemAsync(REFRESH_TOKEN_KEY);
  // Keep the signed-in UI available when only a refresh token remains.
  return token || (refreshToken ? "refresh-pending" : null);
}
export async function saveToken(value: unknown, refreshValue: unknown) {
  // SecureStore accepts strings only. Validate the API response before writing
  // either credential so a partial/old backend response cannot corrupt a session.
  if (typeof value !== "string" || !value.trim()) {
    throw new Error("السيرفر لم يُرجع رمز الدخول بصيغة نصية صحيحة. تأكد من تحديث خدمة المكتب ثم حاول مرة أخرى.");
  }
  if (typeof refreshValue !== "string" || !refreshValue.trim()) {
    throw new Error("السيرفر لم يُرجع رمز تجديد الجلسة. أعد تشغيل خدمة Backend لتفعيل تحديث الجلسات ثم حاول تسجيل الدخول مجددًا.");
  }
  await SecureStore.setItemAsync(TOKEN_KEY, value);
  await SecureStore.setItemAsync(REFRESH_TOKEN_KEY, refreshValue);
  token = value;
  refreshToken = refreshValue;
}
export async function clearToken() {
  token = null;
  refreshToken = null;
  await SecureStore.deleteItemAsync(TOKEN_KEY);
  await SecureStore.deleteItemAsync(REFRESH_TOKEN_KEY);
}

async function renewSession(): Promise<boolean | null> {
  if (refreshPromise) return refreshPromise;
  if (!refreshToken) return false;
  refreshPromise = (async () => {
    try {
      const response = await fetch(API_BASE + "/api/auth/refresh", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });
      const data: any = await response.json().catch(() => ({}));
      if (!response.ok || !data.access_token || !data.refresh_token) {
        await clearToken();
        return false;
      }
      await saveToken(data.access_token, data.refresh_token);
      return true;
    } catch {
      // Keep credentials when the failure is only a temporary network problem.
      return null;
    }
  })();
  try { return await refreshPromise; }
  finally { refreshPromise = null; }
}

export async function api<T>(path: string, options: { method?: string; body?: unknown } = {}): Promise<T> {
  const send = () => {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (token) headers.Authorization = `Bearer ${token}`;
    return fetch(API_BASE + path, {
      method: options.method || "GET", headers,
      ...(options.body !== undefined ? { body: JSON.stringify(options.body) } : {}),
    });
  };
  let response = await send();
  if (response.status === 401 && refreshToken && path !== "/api/auth/refresh" && path !== "/api/auth/login") {
    const renewed = await renewSession();
    if (renewed) response = await send();
    else if (renewed === null) throw new Error("تعذر الاتصال لتجديد الجلسة. تحقق من الإنترنت وحاول مرة أخرى.");
    else throw new Error("انتهت جلسة الدخول. سجّل الدخول مرة أخرى.");
  }
  const data: any = await response.json().catch(() => ({}));
  if (response.status === 401) {
    if (token || refreshToken) await clearToken();
    throw new Error(data.detail || "انتهت جلسة الدخول. سجّل الدخول مرة أخرى.");
  }
  if (!response.ok) throw new Error(data.detail || `خطأ في الاتصال (${response.status})`);
  return data as T;
}

export async function savePushToken(value: unknown) {
  if (typeof value !== "string" || !value.trim()) {
    throw new Error("رمز إشعارات الهاتف غير صالح؛ لم يتم حفظه على الجهاز.");
  }
  await SecureStore.setItemAsync(PUSH_TOKEN_KEY, value);
}
export async function loadPushToken() { return SecureStore.getItemAsync(PUSH_TOKEN_KEY); }
export async function clearPushToken() { await SecureStore.deleteItemAsync(PUSH_TOKEN_KEY); }
