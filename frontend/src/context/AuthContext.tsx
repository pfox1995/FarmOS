import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react';

const API_BASE = 'http://localhost:8000/api/v1';

export interface AuthUser {
  user_id: string;
  name: string;
  email: string;
  onboarding_completed: boolean;
  farmname: string;
  location: string;
  area: number;
  main_crop: string;
  crop_variety: string;
  farmland_type: string;
  farmer_type: string;
  is_promotion_area: boolean;
  has_farm_registration: boolean;
  years_rural_residence: number;
  years_farming: number;
}

interface AuthContextType {
  user: AuthUser | null;
  login: (userId: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
  isAuthenticated: boolean;
  isLoading: boolean;
  needsOnboarding: boolean;
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
        setUser({
          user_id: data.user_id,
          name: data.name,
          email: data.email ?? '',
          onboarding_completed: data.onboarding_completed ?? false,
          farmname: data.farmname ?? '',
          location: data.location ?? '',
          area: data.area ?? 0,
          main_crop: data.main_crop ?? '',
          crop_variety: data.crop_variety ?? '',
          farmland_type: data.farmland_type ?? '',
          farmer_type: data.farmer_type ?? '일반',
          is_promotion_area: data.is_promotion_area ?? false,
          has_farm_registration: data.has_farm_registration ?? false,
          years_rural_residence: data.years_rural_residence ?? 0,
          years_farming: data.years_farming ?? 0,
        });
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
    // 로그인 후 전체 프로필 다시 조회 (onboarding_completed 포함)
    await checkAuth();
  };

  const logout = async () => {
    await fetch(`${API_BASE}/auth/logout`, {
      method: 'POST',
      credentials: 'include',
    });
    setUser(null);
  };

  const refreshUser = useCallback(async () => {
    await checkAuth();
  }, [checkAuth]);

  const needsOnboarding = !!user && !user.onboarding_completed;

  return (
    <AuthContext.Provider value={{ user, login, logout, refreshUser, isAuthenticated: !!user, isLoading, needsOnboarding }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
