"use client";

import { createContext, useContext, useState, type ReactNode } from "react";

const DEFAULT_MESSAGE = "録音（解析）を中断しますか？進行中の内容は失われます。";

interface NavigationGuardContextValue {
  isGuarded: boolean;
  guardMessage: string;
  setGuarded: (guarded: boolean, message?: string) => void;
}

const NavigationGuardContext = createContext<NavigationGuardContextValue | null>(null);

// 録音中・解析中や、未保存の記録が残っている画面で不用意にフッターナビへ
// 移動して内容を失わないようにするためのガード（2026-08-12ユーザー指示、
// 2026-08-15にsummary/logへ拡張）。FooterNavはレイアウト直下、各ページは
// その配下の別コンポーネントなので、両者をつなぐのにcontextが必要 —
// props経由では届かない。message省略時はデフォルト（録音/解析用）の文言。
export function NavigationGuardProvider({ children }: { children: ReactNode }) {
  const [isGuarded, setIsGuarded] = useState(false);
  const [guardMessage, setGuardMessage] = useState(DEFAULT_MESSAGE);

  const setGuarded = (guarded: boolean, message: string = DEFAULT_MESSAGE) => {
    setIsGuarded(guarded);
    if (guarded) setGuardMessage(message);
  };

  return (
    <NavigationGuardContext.Provider value={{ isGuarded, guardMessage, setGuarded }}>
      {children}
    </NavigationGuardContext.Provider>
  );
}

export function useNavigationGuard(): NavigationGuardContextValue {
  const ctx = useContext(NavigationGuardContext);
  if (!ctx) throw new Error("useNavigationGuard must be used within <NavigationGuardProvider>");
  return ctx;
}
