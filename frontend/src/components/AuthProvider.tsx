import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { CLIENT_HEADER, post, setAccessToken, setRefreshHandler } from "../lib/api";

export interface User { id: string; email: string; username: string; role: "student" | "administrator"; is_active: boolean }
interface TokenResponse { access_token: string; user: User }
interface Ctx {
  user: User | null; loading: boolean;
  login: (identifier: string, password: string) => Promise<void>;
  register: (email: string, username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}
export const AuthContext = createContext<Ctx>({ user: null, loading: true, login: async () => undefined, register: async () => undefined, logout: async () => undefined });
export const useAuth = () => useContext(AuthContext);

// One refresh at a time: React dev mode and several callers must never send the same cookie twice.
let inflight: Promise<TokenResponse | null> | null = null;

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async (): Promise<boolean> => {
    inflight ??= post<TokenResponse>("/auth/refresh", undefined, { headers: CLIENT_HEADER }).catch(() => null).finally(() => { setTimeout(() => { inflight = null; }, 0); });
    const r = await inflight;
    setAccessToken(r ? r.access_token : null);
    setUser(r ? r.user : null);
    return !!r;
  }, []);

  useEffect(() => {
    setRefreshHandler(refresh);
    refresh().finally(() => setLoading(false));
    return () => setRefreshHandler(null);
  }, [refresh]);

  const value = useMemo<Ctx>(() => ({
    user, loading,
    login: async (identifier, password) => { const r = await post<TokenResponse>("/auth/login", { identifier, password }); setAccessToken(r.access_token); setUser(r.user); },
    register: async (email, username, password) => {
      await post("/auth/register", { email, username, password });
      const r = await post<TokenResponse>("/auth/login", { identifier: username, password });
      setAccessToken(r.access_token); setUser(r.user);
    },
    logout: async () => { try { await post("/auth/logout", undefined, { headers: CLIENT_HEADER }); } finally { setAccessToken(null); setUser(null); } },
  }), [user, loading]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
