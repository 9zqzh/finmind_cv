import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { api, getToken, setToken } from "../api/client";

interface AuthState {
  loggedIn: boolean;
  username: string | null;
  loading: boolean;
  markLoggedIn: (username: string) => void;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthState>({
  loggedIn: false,
  username: null,
  loading: true,
  markLoggedIn: () => {},
  logout: async () => {},
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [loggedIn, setLoggedIn] = useState(false);
  const [username, setUsername] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // 页面刷新时若本地有 token，向后端确认登录状态
  useEffect(() => {
    if (!getToken()) {
      setLoading(false);
      return;
    }
    api
      .authStatus()
      .then((status) => {
        setLoggedIn(status.logged_in);
        setUsername(status.username);
        if (!status.logged_in) {
          setToken(null);
        }
      })
      .catch(() => setToken(null))
      .finally(() => setLoading(false));
  }, []);

  const markLoggedIn = useCallback((name: string) => {
    setLoggedIn(true);
    setUsername(name);
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.logout();
    } finally {
      setToken(null);
      setLoggedIn(false);
      setUsername(null);
    }
  }, []);

  return (
    <AuthContext.Provider
      value={{ loggedIn, username, loading, markLoggedIn, logout }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
