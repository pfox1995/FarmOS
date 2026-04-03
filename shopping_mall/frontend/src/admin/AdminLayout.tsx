import { useEffect } from 'react';
import { Outlet, NavLink } from 'react-router-dom';
import { useUserStore } from '@/stores/userStore';

const navItems = [
  { to: '/admin', label: '대시보드', icon: '📊', end: true },
  { to: '/admin/chatbot', label: '챗봇 관리', icon: '🤖', end: false },
  { to: '/admin/calendar', label: '판매 캘린더', icon: '📅', end: false },
  { to: '/admin/shipments', label: '배송 관리', icon: '🚚', end: false },
  { to: '/admin/reports', label: '리포트', icon: '📋', end: false },
  { to: '/admin/analytics', label: '분석', icon: '📈', end: false },
  { to: '/admin/expenses', label: '비용 관리', icon: '💰', end: false },
];

export default function AdminLayout() {
  const { user, isLoggedIn, checkAuth } = useUserStore();

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  return (
    <div className="min-h-screen bg-gray-100">
      {/* Sidebar */}
      <aside className="fixed left-0 top-0 h-screen w-60 bg-gray-900 text-white flex flex-col z-50">
        <div className="px-5 py-6 border-b border-gray-700">
          <h1 className="text-lg font-bold tracking-tight">FarmOS 백오피스</h1>
        </div>
        <nav className="flex-1 py-4 overflow-y-auto">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `flex items-center gap-3 px-5 py-3 text-sm transition-colors ${
                  isActive
                    ? 'bg-gray-700 border-l-4 border-[#03C75A] text-white font-semibold'
                    : 'border-l-4 border-transparent text-gray-300 hover:bg-gray-800 hover:text-white'
                }`
              }
            >
              <span>{item.icon}</span>
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>
        <NavLink
          to="/"
          className="px-5 py-3 text-sm text-gray-400 hover:text-white hover:bg-gray-800 transition-colors border-t border-gray-700"
        >
          ← 쇼핑몰로 돌아가기
        </NavLink>
        <div className="px-5 py-4 border-t border-gray-700 text-xs text-gray-500">
          FarmOS Admin v1.0
        </div>
      </aside>

      {/* Main content */}
      <div className="ml-60">
        <header className="h-14 bg-white border-b border-gray-200 flex items-center justify-between px-6 sticky top-0 z-40">
          <div />
          <div className="flex items-center gap-3">
            <span className="text-sm text-gray-600">
              {isLoggedIn && user ? `${user.name} (${user.farmos_user_id})` : '관리자'}
            </span>
            <div className="w-8 h-8 rounded-full bg-[#03C75A] text-white flex items-center justify-center text-sm font-bold">
              {user?.name?.charAt(0) ?? 'A'}
            </div>
          </div>
        </header>
        <main className="min-h-[calc(100vh-3.5rem)]">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
