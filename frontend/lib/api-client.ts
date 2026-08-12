const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

// §5: the access token lives in memory only (module scope), never in
// localStorage/sessionStorage — reduces XSS blast radius. It's lost on a
// full page reload by design; AuthProvider silently re-mints one via the
// httpOnly refresh cookie on mount (see auth-context.tsx).
let accessToken: string | null = null;

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function parseErrorDetail(res: Response): Promise<string> {
  try {
    const body = await res.json();
    if (typeof body.detail === "string") return body.detail;
    if (Array.isArray(body.detail) && body.detail[0]?.msg) return body.detail[0].msg;
  } catch {
    // fall through to generic message
  }
  return "エラーが発生しました。もう一度お試しください。";
}

async function request<T>(path: string, options: RequestInit = {}, allowRetry = true): Promise<T> {
  const headers = new Headers(options.headers);
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  if (options.body && !(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers,
      // Sends the httpOnly refresh-token cookie on /api/auth/* calls (§5).
      credentials: "include",
    });
  } catch {
    // fetch() itself rejects on a network-level failure (offline, backend
    // unreachable, etc.) — distinct from an HTTP error status, and was
    // previously left to propagate as a raw, uncaught TypeError (e.g. out
    // of AuthProvider's logout(), which had no catch to stop it).
    throw new ApiError(0, "通信エラーが発生しました。通信環境をご確認のうえ、もう一度お試しください。");
  }

  if (res.status === 401 && allowRetry && path !== "/api/auth/refresh") {
    const refreshed = await refreshAccessToken();
    if (refreshed) return request<T>(path, options, false);
  }

  if (!res.ok) {
    throw new ApiError(res.status, await parseErrorDetail(res));
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

async function attemptRefresh(): Promise<Response | null> {
  try {
    return await fetch(`${API_BASE_URL}/api/auth/refresh`, {
      method: "POST",
      credentials: "include",
    });
  } catch {
    return null;
  }
}

// A network-level failure here (backend momentarily unreachable — e.g. a
// deploy restart) is not proof the session is invalid, but AuthProvider
// only calls this once, on mount, with no retry of its own. Treating a
// single blip the same as "not logged in" left a tab permanently showing
// logged-out (header/footer gone, protected pages bouncing back) until
// the next full reload happened to land outside the failure window — a
// real 401 (revoked/expired refresh token) means don't bother retrying.
const _RETRY_DELAYS_MS = [500, 1000];

export async function refreshAccessToken(): Promise<boolean> {
  let res = await attemptRefresh();
  for (let i = 0; res === null && i < _RETRY_DELAYS_MS.length; i++) {
    await new Promise((resolve) => setTimeout(resolve, _RETRY_DELAYS_MS[i]));
    res = await attemptRefresh();
  }

  if (res === null || !res.ok) {
    accessToken = null;
    return false;
  }
  const data = (await res.json()) as { access_token: string };
  accessToken = data.access_token;
  return true;
}

export const apiClient = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body !== undefined ? JSON.stringify(body) : undefined }),
  postForm: <T>(path: string, form: FormData) => request<T>(path, { method: "POST", body: form }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};
