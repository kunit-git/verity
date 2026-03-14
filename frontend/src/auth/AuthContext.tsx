import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from "react";
import { useQueryClient } from "@tanstack/react-query";
import type { User } from "../types";
import * as authApi from "../api/auth";
import * as vaultsApi from "../api/vaults";

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  register: (
    username: string,
    email: string,
    password: string
  ) => Promise<void>;
  logout: () => void;
  selectVault: (vaultId: string) => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const queryClient = useQueryClient();

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (token) {
      authApi
        .getMe()
        .then(setUser)
        .catch(() => {
          authApi.logout();
          setUser(null);
        })
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    await authApi.login(username, password);
    const me = await authApi.getMe();
    setUser(me);
  }, []);

  const register = useCallback(
    async (username: string, email: string, password: string) => {
      await authApi.register(username, email, password);
      await authApi.login(username, password);
      const me = await authApi.getMe();
      setUser(me);
    },
    []
  );

  const logout = useCallback(() => {
    authApi.logout();
    setUser(null);
    queryClient.clear();
  }, [queryClient]);

  const selectVault = useCallback(
    async (vaultId: string) => {
      await vaultsApi.selectVault(vaultId);
      const me = await authApi.getMe();
      setUser(me);
      queryClient.clear();
    },
    [queryClient]
  );

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, selectVault }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
