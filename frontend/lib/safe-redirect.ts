/**
 * Validates that `path` is a same-origin relative path before it's ever
 * passed to router.push/replace. The `next` query param round-trips
 * through URLs a user can be sent (e.g. a phishing link like
 * `/login?next=https://evil.example`), and Next.js's router genuinely
 * performs a full external navigation for an absolute URL — confirmed
 * against node_modules/next/dist/client/components/router-reducer/
 * reducers/navigate-reducer.js's isExternalUrl -> completeHardNavigation
 * path, which sets `mpaNavigation: true`. Rejects anything that isn't a
 * single leading "/" (protocol-relative "//host" and backslash-based
 * "/\host" tricks browsers normalize into an absolute URL are excluded
 * too), falling back to a known-safe internal path instead.
 */
export function safeInternalPath(path: string | null, fallback: string): string {
  if (!path) return fallback;
  if (!path.startsWith("/") || path.startsWith("//") || path.startsWith("/\\")) {
    return fallback;
  }
  return path;
}
