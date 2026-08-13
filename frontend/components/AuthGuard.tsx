"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAuth } from "@/lib/auth-context";

/**
 * Second layer of the (authed) route group's auth gate — see
 * app/(authed)/layout.tsx for the first (server-side, cookie-presence-only)
 * layer. That layer only catches a *missing* refresh cookie; a *stale/
 * invalid* one still lets the request through (it can't validate the
 * token itself — see auth-context.tsx), so this client-side check is what
 * actually catches that case, the same way scene/page.tsx's one-off
 * version did before every (authed) route was wrapped here.
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
