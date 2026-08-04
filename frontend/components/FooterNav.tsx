"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth-context";

const NAV_ITEMS = [
  {
    href: "/scene",
    label: "会話サポート",
    activeMatch: (path: string) => path === "/" || path.startsWith("/scene") || path.startsWith("/conversation"),
    icon: (
      <path d="M4 19V9l8-4 8 4v10M9 19v-6h6v6" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    ),
  },
  {
    href: "/check",
    label: "発言チェック",
    activeMatch: (path: string) => path.startsWith("/check"),
    icon: (
      <path
        d="M20 12a8 8 0 1 1-3.1-6.3M20 5v4h-4m-7 3 2 2 4-4"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    ),
  },
  {
    href: "/history",
    label: "今までの記録",
    activeMatch: (path: string) => path.startsWith("/history"),
    icon: (
      <>
        <path d="M12 7v5l3.2 1.9" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" fill="none" />
        <circle cx="12" cy="12" r="8.2" strokeWidth="1.6" fill="none" />
      </>
    ),
  },
  {
    href: "/settings",
    label: "設定",
    activeMatch: (path: string) => path.startsWith("/settings"),
    icon: (
      <>
        <circle cx="12" cy="12" r="2.6" strokeWidth="1.6" fill="none" />
        <path
          d="M12 4.2v1.7M12 18v1.8M19.8 12h-1.7M5.9 12H4.2M17.3 6.7l-1.2 1.2M7.9 16.1l-1.2 1.2M17.3 17.3l-1.2-1.2M7.9 7.9 6.7 6.7"
          strokeWidth="1.6"
          strokeLinecap="round"
        />
      </>
    ),
  },
];

// §11.1: shown on every screen once authenticated, hidden while logged
// out (login/register/etc. don't have it at all).
export function FooterNav() {
  const { isAuthenticated } = useAuth();
  const pathname = usePathname();

  if (!isAuthenticated) return null;

  return (
    <nav className="grid grid-cols-4 border-t border-line bg-surface-sunken px-1 pb-3 pt-2">
      {NAV_ITEMS.map((item) => {
        const isCurrent = item.activeMatch(pathname);
        return (
          <Link
            key={item.href}
            href={item.href}
            className={`flex flex-col items-center gap-1 py-1 text-[10px] ${
              isCurrent ? "font-bold text-ink" : "text-ink-soft"
            }`}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" className="h-5 w-5">
              {item.icon}
            </svg>
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
