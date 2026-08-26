import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { api, getToken, onAuthExpired, setToken } from "../api/client";

interface AuthState {
  loggedIn: boolean;
  username: string | null;
  isAdmin: boolean;
  isSuperAdmin: boolean;
  loading: boolean;
  markLoggedIn: (username: string, isAdmin: boolean, isSuperAdmin: boolean) => void;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthState>({
  loggedIn: false,
  username: null,
  isAdmin: false,
  isSuperAdmin: false,
  loading: true,
  markLoggedIn: () => {},
  logout: async () => {},
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [loggedIn, setLoggedIn] = useState(false);
  const [username, setUsername] = useState<string | null>(null);
  const [isAdmin, setIsAdmin] = useState(false);
  const [isSuperAdmin, setIsSuperAdmin] = useState(false);
  const [loading, setLoading] = useState(true);

  // 页面刷新时若本地有 token，向后端确认登录状态
  useEffect(() => {
    const unsubscribe = onAuthExpired(() => {
      setLoggedIn(false);
      setUsername(null);
      setIsAdmin(false);
      setIsSuperAdmin(false);
      setLoading(false);
    });
    if (!getToken()) {
      setLoading(false);
      return unsubscribe;
    }
    api
      .authStatus()
      .then((status) => {
        setLoggedIn(status.logged_in);
        setUsername(status.username);
        setIsAdmin(status.is_admin);
        setIsSuperAdmin(status.is_super_admin);
        if (!status.logged_in) {
          setToken(null);
        }
      })
      .catch(() => {
        setToken(null);
        setLoggedIn(false);
        setUsername(null);
        setIsAdmin(false);
        setIsSuperAdmin(false);
      })
      .finally(() => setLoading(false));
    return unsubscribe;
  }, []);

  const markLoggedIn = useCallback((name: string, admin: boolean, superAdmin: boolean) => {
    setLoggedIn(true);
    setUsername(name);
    setIsAdmin(admin);
    setIsSuperAdmin(superAdmin);
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.logout();
    } finally {
      setToken(null);
      setLoggedIn(false);
      setUsername(null);
      setIsAdmin(false);
      setIsSuperAdmin(false);
    }
  }, []);

  return (
    <AuthContext.Provider
      value={{ loggedIn, username, isAdmin, isSuperAdmin, loading, markLoggedIn, logout }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
