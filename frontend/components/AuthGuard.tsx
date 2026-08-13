"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAuth } from "@/lib/auth-context";

/**
 * The (authed) route group's entire auth gate — see app/(authed)/layout.tsx
 * for why this is client-side only (frontend and backend intentionally
 * don't share a parent domain, so the refresh cookie never reaches the
 * frontend's own server; a server-side check would always see "no
 * cookie", even for a genuinely logged-in visitor). Same pattern
 * scene/page.tsx used one-off before every (authed) route was wrapped
 * here.
 */
export function AuthGuard({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace(`/login?next=${encodeURIComponent(pathname)}`);
    }
  }, [isLoading, isAuthenticated, pathname, router]);

  if (isLoading || !isAuthenticated) return null;
  return <>{children}</>;
}
