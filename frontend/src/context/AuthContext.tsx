import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react';

const API_BASE = 'http://localhost:8000/api/v1';

interface AuthUser {
  user_id: string;
  name: string;
}

interface AuthContextType {
  user: AuthUser | null;
  login: (userId: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  isAuthenticated: boolean;
  isLoading: boolean;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // 앱 시작 시 쿠키 기반으로 서버에 인증 상태 확인
  const checkAuth = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/auth/me`, { credentials: 'include' });
      if (res.ok) {
        const data = await res.json();
        setUser({ user_id: data.user_id, name: data.name });
      } else {
        // 인증 실패 시 만료/무효 쿠키 정리
        await fetch(`${API_BASE}/auth/logout`, { method: 'POST', credentials: 'include' }).catch(() => {});
        setUser(null);
      }
    } catch {
      setUser(null);
    }
    setIsLoading(false);
  }, []);

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  // Periodic session re-validation — detects backend restart
  useEffect(() => {
    if (!user) return;
    const interval = setInterval(checkAuth, 30_000);
    return () => clearInterval(interval);
  }, [user, checkAuth]);

  const login = async (userId: string, password: string) => {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ user_id: userId, password }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || '로그인에 실패했습니다.');
    }
    const data = await res.json();
    setUser({ user_id: data.user_id, name: data.name });
  };

  const logout = async () => {
    await fetch(`${API_BASE}/auth/logout`, {
      method: 'POST',
      credentials: 'include',
    });
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, login, logout, isAuthenticated: !!user, isLoading }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
