import { create } from 'zustand';

const FARMOS_API = 'http://localhost:8000/api/v1';
const SHOP_API = import.meta.env.VITE_API_URL || 'http://localhost:4000';

interface AuthUser {
  farmos_user_id: string;
  name: string;
  shop_user_id: number | null;
}

interface UserState {
  user: AuthUser | null;
  isLoggedIn: boolean;
  isLoading: boolean;
  checkAuth: () => Promise<void>;
  logout: () => Promise<void>;
}

export const useUserStore = create<UserState>((set) => ({
  user: null,
  isLoggedIn: false,
  isLoading: true,

  checkAuth: async () => {
    try {
      // 쇼핑몰 백엔드가 FarmOS 백엔드에 서버사이드 검증 수행
      const res = await fetch(`${SHOP_API}/api/users/auth/status`, {
        credentials: 'include',
      });
      if (res.ok) {
        const data = await res.json();
        if (data.authenticated) {
          set({
            user: {
              farmos_user_id: data.farmos_user_id,
              name: data.name,
              shop_user_id: data.shop_user_id,
            },
            isLoggedIn: true,
            isLoading: false,
          });
          return;
        }
      }
    } catch {
      // 무시
    }
    set({ user: null, isLoggedIn: false, isLoading: false });
  },

  logout: async () => {
    // FarmOS 쿠키 삭제 (같은 localhost 도메인)
    try {
      await fetch(`${FARMOS_API}/auth/logout`, {
        method: 'POST',
        credentials: 'include',
      });
    } catch {
      // 무시
    }
    set({ user: null, isLoggedIn: false });
  },
}));
