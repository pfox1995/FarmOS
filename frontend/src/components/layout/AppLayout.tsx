import { Outlet, useLocation } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import Sidebar from './Sidebar';
import TopBar from './TopBar';
import MobileNav from './MobileNav';

const PAGE_TITLES: Record<string, string> = {
  '/': '대시보드',
  '/diagnosis': '병해충 AI 진단',
  '/iot': 'IoT 센서 대시보드',
  '/reviews': '리뷰 분석 리포트',
  '/documents': '행정 서류 자동 생성',
  '/weather': '기상 연동 스케줄링',
  '/harvest': '수확량 예측',
  '/journal': '영농일지',
  '/market': '농산물 시세 정보',
  '/scenario': '사과 농장 한 달 시나리오',
};

export default function AppLayout() {
  const { pathname } = useLocation();
  const title = PAGE_TITLES[pathname] || 'FarmOS 2.0';

  return (
    <div className="flex min-h-screen">
      {/* Desktop Sidebar */}
      <div className="hidden lg:block">
        <Sidebar />
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col min-w-0">
        <TopBar title={title} />
        <main className="flex-1 overflow-y-auto bg-surface p-3 sm:p-4 lg:p-8 pb-[80px] lg:pb-8">
          <AnimatePresence mode="wait">
            <motion.div
              key={pathname}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.2, ease: 'easeOut' }}
            >
              <Outlet />
            </motion.div>
          </AnimatePresence>
        </main>
        <MobileNav />
      </div>
    </div>
  );
}
