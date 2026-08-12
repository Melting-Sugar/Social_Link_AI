"use client";

import { createContext, useContext, useState, type ReactNode } from "react";

interface NavigationGuardContextValue {
  isGuarded: boolean;
  setGuarded: (guarded: boolean) => void;
}

const NavigationGuardContext = createContext<NavigationGuardContextValue | null>(null);

// 録音中・解析中に不用意にフッターナビへ移動して結果を失わないようにする
// ためのガード（2026-08-12ユーザー指示）。FooterNavはレイアウト直下、
// ConversationPageはその配下の別コンポーネントなので、両者をつなぐのに
// contextが必要 — props経由では届かない。
export function NavigationGuardProvider({ children }: { children: ReactNode }) {
  const [isGuarded, setGuarded] = useState(false);
  return (
    <NavigationGuardContext.Provider value={{ isGuarded, setGuarded }}>{children}</NavigationGuardContext.Provider>
  );
}

export function useNavigationGuard(): NavigationGuardContextValue {
  const ctx = useContext(NavigationGuardContext);
  if (!ctx) throw new Error("useNavigationGuard must be used within <NavigationGuardProvider>");
  return ctx;
}
