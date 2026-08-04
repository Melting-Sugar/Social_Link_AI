"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { FooterNav } from "@/components/FooterNav";
import { AuthProvider } from "@/lib/auth-context";

export function Providers({ children }: { children: React.ReactNode }) {
  // One QueryClient per browser session (not per render) — created lazily
  // in state so it survives re-renders but isn't shared across users on
  // the server (moot here since this is a client component, but keeps the
  // pattern correct if anything above it ever changes).
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            // §11.6: progressive reveal relies on callers opting individual
            // queries into polling via refetchInterval — no global default
            // here so non-polling queries (e.g. GET /api/users/me) don't
            // refetch needlessly.
            retry: 1,
          },
        },
      })
  );

  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <div className="flex min-h-full flex-1 flex-col">
          <div className="flex flex-1 flex-col">{children}</div>
          <FooterNav />
        </div>
      </AuthProvider>
    </QueryClientProvider>
  );
}
