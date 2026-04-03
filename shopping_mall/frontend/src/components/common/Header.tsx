import { Link } from 'react-router-dom';
import SearchBar from './SearchBar';
import { useCart } from '@/hooks/useCart';
import { useUserStore } from '@/stores/userStore';

const FARMOS_LOGIN_URL = 'http://localhost:5173/login';

export default function Header() {
  const { data: cart } = useCart();
  const itemCount = cart?.items.length ?? 0;
  const { user, isLoggedIn, isLoading, logout } = useUserStore();

  const handleLogin = () => {
    // FarmOS 로그인 페이지로 이동 (로그인 후 돌아올 수 있도록 현재 URL 전달)
    window.location.href = `${FARMOS_LOGIN_URL}?redirect=${encodeURIComponent(window.location.href)}`;
  };

  const handleLogout = async () => {
    await logout();
    window.location.reload();
  };

  return (
    <header className="sticky top-0 z-50 bg-white border-b border-gray-200">
      <div className="max-w-6xl mx-auto px-4 h-16 flex items-center justify-between gap-4">
        <Link to="/" className="text-xl font-bold text-[#03C75A] whitespace-nowrap">
          FarmOS 마켓
        </Link>
        <div className="flex-1 max-w-xl">
          <SearchBar />
        </div>
        <nav className="flex items-center gap-4 text-sm whitespace-nowrap">
          <Link to="/cart" className="relative hover:text-[#03C75A]">
            장바구니
            {itemCount > 0 && (
              <span className="absolute -top-2 -right-3 bg-red-500 text-white text-xs rounded-full w-5 h-5 flex items-center justify-center">
                {itemCount}
              </span>
            )}
          </Link>
          {isLoading ? null : isLoggedIn && user ? (
            <>
              <Link to="/mypage" className="hover:text-[#03C75A]">마이페이지</Link>
              <span className="text-gray-500">{user.name}님</span>
              <button
                onClick={handleLogout}
                className="text-gray-400 hover:text-red-500 transition-colors"
              >
                로그아웃
              </button>
            </>
          ) : (
            <button
              onClick={handleLogin}
              className="bg-[#03C75A] text-white px-4 py-1.5 rounded text-sm font-medium hover:bg-[#02b050] transition-colors"
            >
              로그인
            </button>
          )}
        </nav>
      </div>
    </header>
  );
}
