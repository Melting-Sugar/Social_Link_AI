"use client";

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { refreshAccessToken, setAccessToken } from "./api-client";
import { authApi } from "./auth-api";

interface AuthContextValue {
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (accessToken: string) => void;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // §5: on every fresh page load the in-memory access token is gone —
    // silently try to mint a new one from the httpOnly refresh cookie
    // before deciding whether the user is logged in.
    refreshAccessToken()
      .then(setIsAuthenticated)
      .finally(() => setIsLoading(false));
  }, []);

  const login = useCallback((token: string) => {
    setAccessToken(token);
    setIsAuthenticated(true);
  }, []);

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } catch {
      // Best-effort: a network failure here shouldn't stop the caller from
      // navigating to /login below — we still drop local auth state either
      // way, and a still-valid server-side session cookie left behind by a
      // failed call expires on its own.
    } finally {
      setAccessToken(null);
      setIsAuthenticated(false);
    }
  }, []);

  return (
    <AuthContext.Provider value={{ isAuthenticated, isLoading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within <AuthProvider>");
  return ctx;
}
