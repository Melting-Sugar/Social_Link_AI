"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAuth } from "@/lib/auth-context";

/**
 * Client-side mirror of AuthGuard, for the (guest) route group
 * (login/register/forgot-username/forgot-password): redirects home if a
 * session already exists. Entirely client-side because the frontend and
 * backend deliberately don't share a parent domain (Fly.io's *.fly.dev
 * vs Cloudflare's *.workers.dev — no COOKIE_DOMAIN value can bridge two
 * unrelated domains), so the refresh cookie never reaches the frontend's
 * own server at all; a server-side cookies() check here would always see
 * "no cookie" even for a genuinely logged-in visitor and never redirect
 * them away from the login form. The real credential is the Bearer
 * access token, exchanged over a normal cross-origin fetch — unaffected
 * by any of this.
 */
export function GuestGuard({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && isAuthenticated) {
      router.replace("/");
    }
  }, [isLoading, isAuthenticated, router]);

  if (isLoading || isAuthenticated) return null;
  return <>{children}</>;
}
