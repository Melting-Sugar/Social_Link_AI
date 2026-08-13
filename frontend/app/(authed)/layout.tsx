import { AuthGuard } from "@/components/AuthGuard";

// Replaces proxy.ts's gate for every route that requires a session
// (everything except (guest)/, reset-password, terms, privacy — see
// app/(guest)/layout.tsx for the mirror-image check). Next.js 16 locked
// Proxy to the Node.js runtime with no way to opt back into Edge (see
// node_modules/next/dist/docs/.../file-conventions/proxy.md, "Runtime"
// section) — a runtime OpenNext's Cloudflare adapter doesn't yet support.
//
// This used to also do a server-side `cookies().has("refresh_token")`
// check before rendering anything, mirroring proxy.ts's own "cheap
// presence check, not real validation" property. Dropped once the
// deploy topology was settled: frontend (Cloudflare) and backend
// (Fly.io) sit on unrelated domains by design, so the refresh cookie —
// scoped to the backend's own origin — never reaches this server at
// all; the check would always see "missing" even for a genuinely
// logged-in visitor and permanently redirect everyone to /login. Every
// route in this group is a client component with no server-side data
// fetching (confirmed by inspection), so AuthGuard alone is safe: the
// brief shell rendered before its client-side check redirects never
// contains real data, only whatever that page's initial (pre-fetch)
// render already looked like.
export default function AuthedLayout({ children }: { children: React.ReactNode }) {
  return <AuthGuard>{children}</AuthGuard>;
}
