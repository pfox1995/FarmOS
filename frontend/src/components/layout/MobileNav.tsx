import { NavLink, useNavigate } from 'react-router-dom';
import { MdMoreHoriz, MdLogout } from 'react-icons/md';
import { useState } from 'react';
import { useAuth } from '@/context/AuthContext';

const MAIN_TABS = [
  { to: '/', icon: '/images/icons/dashboard.jpg', label: '홈' },
  { to: '/diagnosis', icon: '/images/icons/diagnosis.jpg', label: '진단' },
  { to: '/iot', icon: '/images/icons/iot-sensors.jpg', label: '센서' },
  { to: '/weather', icon: '/images/icons/weather.jpg', label: '기상' },
];

const MORE_TABS: { to: string; icon: string; label: string }[] = [
  { to: '/reviews', icon: '/images/icons/reviews.jpg', label: '리뷰 분석' },
  { to: '/documents', icon: '/images/icons/documents.jpg', label: '행정 서류' },
  { to: '/harvest', icon: '/images/icons/harvest.jpg', label: '수확 예측' },
  { to: '/journal', icon: '/images/icons/journal.jpg', label: '영농일지' },
  { to: '/market', icon: '/images/icons/harvest.jpg', label: '시세 정보' },
  { to: '/scenario', icon: '/images/icons/scenario.jpg', label: '시나리오' },
];

export default function MobileNav() {
  const [showMore, setShowMore] = useState(false);
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    setShowMore(false);
    await logout();
    navigate('/login');
  };

  return (
    <>
      {/* More menu overlay */}
      {showMore && (
        <div className="fixed inset-0 z-40 lg:hidden" onClick={() => setShowMore(false)}>
          <div className="absolute inset-0 bg-black/30" />
          <div
            className="absolute bottom-[64px] left-0 right-0 bg-white rounded-t-2xl shadow-lg p-4 pb-5"
            onClick={e => e.stopPropagation()}
          >
            {/* User info — 클릭하면 프로필 */}
            <NavLink
              to="/profile"
              onClick={() => setShowMore(false)}
              className="flex items-center gap-3 px-2 pb-3 mb-3 border-b border-gray-100"
            >
              <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center text-lg">
                🧑‍🌾
              </div>
              <div className="flex-1 min-w-0">
                <p className="font-bold text-gray-900 truncate">{user?.name}</p>
                <p className="text-xs text-gray-400">{user?.user_id}</p>
              </div>
              <span className="text-gray-300">›</span>
            </NavLink>

            {/* Menu grid */}
            <div className="grid grid-cols-3 gap-3">
              {MORE_TABS.map((tab) => (
                <NavLink
                  key={tab.to}
                  to={tab.to}
                  onClick={() => setShowMore(false)}
                  className={({ isActive }) =>
                    `flex flex-col items-center gap-1.5 p-4 rounded-xl transition-colors ${isActive ? 'bg-primary/10 text-primary' : 'text-gray-500 hover:bg-gray-50'
                    }`
                  }
                >
                  <img src={tab.icon} alt={tab.label} className="w-8 h-8 rounded object-cover" />
                  <span className="text-xs font-medium">{tab.label}</span>
                </NavLink>
              ))}
            </div>

            {/* 프로필 + 로그아웃 */}
            <div className="mt-3 flex gap-2">
              <NavLink
                to="/profile"
                onClick={() => setShowMore(false)}
                className="flex-1 flex items-center justify-center gap-2 py-3 rounded-xl bg-primary/5 text-primary font-semibold transition hover:bg-primary/20"
              >
                <span>👤</span>
                <span className="text-base">내 프로필</span>
              </NavLink>
              <button
                onClick={handleLogout}
                className="flex items-center justify-center gap-2 px-5 py-3 rounded-xl text-gray-500 hover:text-danger hover:bg-danger/5 transition cursor-pointer"
              >
                <MdLogout className="text-xl" />
                <span className="text-base font-medium">로그아웃</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Bottom tab bar */}
      <nav className="fixed bottom-0 left-0 right-0 h-[64px] bg-white border-t border-gray-200 flex items-center justify-around z-50 lg:hidden">
        {MAIN_TABS.map(({ to, icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `flex flex-col items-center gap-1 min-w-[64px] py-2 ${isActive ? 'text-primary' : 'text-gray-400'
              }`
            }
          >
            <img src={icon} alt={label} className="w-7 h-7 rounded object-cover" />
            <span className="text-xs font-medium">{label}</span>
          </NavLink>
        ))}
        <button
          onClick={() => setShowMore(!showMore)}
          className={`flex flex-col items-center gap-1 min-w-[64px] py-2 cursor-pointer ${showMore ? 'text-primary' : 'text-gray-400'
            }`}
        >
          <MdMoreHoriz className="text-[28px]" />
          <span className="text-xs font-medium">더보기</span>
        </button>
      </nav>
    </>
  );
}
