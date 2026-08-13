import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { AuthGuard } from "@/components/AuthGuard";

// Replaces proxy.ts's server-side gate for every route that requires a
// session (everything except (guest)/, reset-password, terms, privacy —
// see app/(guest)/layout.tsx for the mirror-image check). Next.js 16
// locked Proxy to the Node.js runtime with no way to opt back into Edge
// (see node_modules/next/dist/docs/.../file-conventions/proxy.md, "Runtime"
// section) — a runtime OpenNext's Cloudflare adapter doesn't yet support.
// A layout Server Component isn't Proxy, so it isn't affected.
//
// This only catches a *missing* refresh cookie — cheap, and blocks
// rendering before any protected content is ever sent, same guarantee
// proxy.ts gave. It cannot validate the cookie itself (no signature/expiry
// check possible server-side without a DB round trip on every navigation);
// a stale/invalid-but-present cookie is caught by AuthGuard instead, once
// the real Bearer-token refresh fails client-side.
const REFRESH_COOKIE_NAME = "refresh_token";

export default async function AuthedLayout({ children }: { children: React.ReactNode }) {
  const cookieStore = await cookies();
  if (!cookieStore.has(REFRESH_COOKIE_NAME)) {
    redirect("/login");
  }

  return <AuthGuard>{children}</AuthGuard>;
}
