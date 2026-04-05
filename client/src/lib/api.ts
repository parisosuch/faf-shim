const BASE_URL = import.meta.env.PUBLIC_API_URL ?? "http://localhost:8000";

/**
 * Parse a UTC datetime string from the API. SQLite-backed timestamps may lack
 * a timezone suffix, so we append "Z" when none is present so the browser
 * treats them as UTC rather than local time.
 */
export function parseUTC(s: string): Date {
  if (!s.endsWith("Z") && !/[+-]\d{2}:\d{2}$/.test(s)) {
    return new Date(s + "Z");
  }
  return new Date(s);
}

function getToken(): string | null {
  if (typeof localStorage === "undefined") return null;
  return localStorage.getItem("token");
}

type RequestOptions = Omit<RequestInit, "body"> & { body?: unknown };

export async function api<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const token = getToken();
  const { body, ...rest } = options;

  const res = await fetch(`${BASE_URL}${path}`, {
    ...rest,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
    ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
  });

  if (res.status === 401) {
    localStorage.removeItem("token");
    window.location.href = "/login";
    throw new Error("Unauthorized");
  }

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `HTTP ${res.status}`);
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}
