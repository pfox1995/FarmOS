import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';

const NAV_ITEMS = [
  { to: '/', icon: '/images/icons/dashboard.jpg', label: '대시보드' },
  { to: '/diagnosis', icon: '/images/icons/diagnosis.jpg', label: '병해충 진단' },
  { to: '/iot', icon: '/images/icons/iot-sensors.jpg', label: 'IoT 센서' },
  { to: '/reviews', icon: '/images/icons/reviews.jpg', label: '리뷰 분석' },
  { to: '/documents', icon: '/images/icons/documents.jpg', label: '행정 서류' },
  { to: '/weather', icon: '/images/icons/weather.jpg', label: '기상 스케줄' },
  { to: '/harvest', icon: '/images/icons/harvest.jpg', label: '수확 예측' },
  { to: '/journal', icon: '/images/icons/journal.jpg', label: '영농일지' },
  { to: '/market', icon: '/images/icons/harvest.jpg', label: '시세 정보' },
  { to: '/scenario', icon: '/images/icons/scenario.jpg', label: '시나리오' },
];

export default function Sidebar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  return (
    <aside className="w-[280px] bg-white border-r border-gray-200 h-screen sticky top-0 flex flex-col overflow-y-auto">
      {/* User Card + 프로필 버튼 */}
      <div className="p-5 border-b border-gray-100">
        <div className="flex items-center gap-3">
          <div className="w-14 h-14 rounded-full bg-primary/10 flex items-center justify-center text-2xl">
            🧑‍🌾
          </div>
          <div className="flex-1 min-w-0">
            <p className="font-bold text-lg text-gray-900">{user?.name}</p>
            <p className="text-sm text-gray-500">{user?.user_id}</p>
          </div>
        </div>
        <NavLink
          to="/profile"
          className={({ isActive }) =>
            `mt-3 flex items-center justify-center gap-2 w-full py-2.5 rounded-xl text-sm font-semibold transition-all ${
              isActive
                ? 'bg-primary/20 text-primary ring-1 ring-primary/30'
                : 'bg-primary/5 text-primary hover:bg-primary/15'
            }`
          }
        >
          <span>👤</span>
          <span>내 프로필</span>
        </NavLink>
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-2">
        {NAV_ITEMS.map(({ to, icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-4 px-5 py-3 min-h-[52px] text-lg transition-colors ${
                isActive
                  ? 'bg-primary/10 text-primary font-bold border-l-4 border-primary'
                  : 'text-gray-700 hover:bg-gray-50 hover:text-gray-900 border-l-4 border-transparent'
              }`
            }
          >
            <img src={icon} alt={label} className="w-7 h-7 rounded-md object-cover flex-shrink-0" />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="p-4 border-t border-gray-100">
        {user && (
          <button
            onClick={handleLogout}
            className="w-full mb-2 px-4 py-2.5 text-base text-gray-600 hover:text-danger hover:bg-danger/5 rounded-xl transition flex items-center justify-center gap-2"
          >
            <span>🚪</span>
            <span>로그아웃</span>
          </button>
        )}
        <p className="text-xs text-gray-400 text-center">FarmOS 2.0 POC</p>
        <p className="text-xs text-gray-300 text-center">Harness Engineering</p>
      </div>
    </aside>
  );
}
