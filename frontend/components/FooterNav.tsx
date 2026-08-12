"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { useNavigationGuard } from "@/lib/navigation-guard-context";

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
  const { isGuarded } = useNavigationGuard();
  const pathname = usePathname();
  const router = useRouter();
  const [pendingHref, setPendingHref] = useState<string | null>(null);

  if (!isAuthenticated) return null;

  const handleNavClick = (e: React.MouseEvent, href: string) => {
    if (!isGuarded) return;
    e.preventDefault();
    setPendingHref(href);
  };

  return (
    <>
      <nav className="grid grid-cols-4 border-t border-line bg-surface-sunken px-1 pb-3 pt-2">
        {NAV_ITEMS.map((item) => {
          const isCurrent = item.activeMatch(pathname);
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={(e) => handleNavClick(e, item.href)}
              className={`flex flex-col items-center gap-1 rounded-xl py-1 text-[10px] transition-colors active:bg-line ${
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

      {pendingHref && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 px-6">
          <div className="w-full max-w-xs rounded-2xl border border-line bg-surface p-4 shadow-app">
            <p className="text-[13px] leading-relaxed text-ink">
              録音（解析）を中断しますか？進行中の内容は失われます。
            </p>
            <div className="mt-3.5 flex gap-2">
              <button
                type="button"
                onClick={() => setPendingHref(null)}
                className="flex-1 rounded-2xl border border-line bg-surface px-3.5 py-2.5 text-[12.5px] font-bold text-ink transition-colors active:bg-surface-sunken"
              >
                キャンセル
              </button>
              <button
                type="button"
                onClick={() => {
                  const href = pendingHref;
                  setPendingHref(null);
                  router.push(href);
                }}
                className="flex-1 rounded-2xl bg-caution px-3.5 py-2.5 text-[12.5px] font-bold text-on-accent transition-colors active:bg-caution-strong"
              >
                はい
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
