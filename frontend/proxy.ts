import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// Next.js 16 renamed middleware.ts -> proxy.ts (same behavior, new name —
// see node_modules/next/dist/docs/.../file-conventions/proxy.md).

const REFRESH_COOKIE_NAME = "refresh_token";

// §11.4: pages usable without a session. /terms (and /privacy once built)
// are here too — legal documents should be readable by a prospective user
// who hasn't registered yet, not just from within the authenticated
// settings screen that happens to link to them.
const PUBLIC_PATHS = [
  "/login",
  "/register",
  "/forgot-username",
  "/forgot-password",
  "/reset-password",
  "/terms",
  "/privacy",
];

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const isPublicPath = PUBLIC_PATHS.some((p) => pathname === p || pathname.startsWith(`${p}/`));
  // §5: only a cheap presence check — proxy can't validate the token's
  // signature/expiry itself (the access token lives in browser JS memory,
  // never in a cookie proxy can read). A stale/invalid cookie still lets
  // a request through here; the actual API calls the page makes will 401
  // and the client-side auth context handles that. This is "is there any
  // reason to think they're logged out", not full authorization.
  const hasRefreshCookie = request.cookies.has(REFRESH_COOKIE_NAME);

  if (!isPublicPath && !hasRefreshCookie) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("next", pathname);
    return NextResponse.redirect(loginUrl);
  }

  const AUTH_ONLY_REDIRECT_EXEMPT = ["/reset-password", "/terms", "/privacy"];
  const isExemptFromAuthRedirect = AUTH_ONLY_REDIRECT_EXEMPT.some(
    (p) => pathname === p || pathname.startsWith(`${p}/`),
  );

  if (isPublicPath && hasRefreshCookie && !isExemptFromAuthRedirect) {
    // Already have a session — no reason to show login/register again.
    // /reset-password is exempt: it's reached via an emailed link and
    // must work even for an already-logged-in browser. /terms and /privacy
    // are exempt for the opposite reason this whole block exists — they're
    // legal documents a logged-in user (settings tab, voice-enroll) needs
    // to reach too, not just a logged-out visitor.
    return NextResponse.redirect(new URL("/", request.url));
  }

  // §12.3: the "声紋未登録なら/voice-enrollへ" redirect is NOT done here —
  // it needs a real API call (GET /api/voice-profile) with the Bearer
  // access token, which only exists in browser memory, not in anything
  // proxy can read server-side. That check is done client-side instead,
  // in scene/page.tsx (the entry point to the conversation-support flow).

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
};
