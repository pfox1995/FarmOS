import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster, ToastBar, toast } from 'react-hot-toast';
import { MdClose } from 'react-icons/md';
import { ScenarioProvider } from '@/context/ScenarioContext';
import { AuthProvider, useAuth } from '@/context/AuthContext';
import AppLayout from '@/components/layout/AppLayout';
import DashboardPage from '@/pages/DashboardPage';
import DiagnosisPage from '@/modules/diagnosis/DiagnosisPage';
import IoTDashboardPage from '@/modules/iot/IoTDashboardPage';
import ReviewsPage from '@/modules/reviews/ReviewsPage';
import DocumentsPage from '@/modules/documents/DocumentsPage';
import WeatherPage from '@/modules/weather/WeatherPage';
import HarvestPage from '@/modules/harvest/HarvestPage';
import JournalPage from '@/modules/journal/JournalPage';
import MarketPricePage from '@/modules/market/MarketPricePage';
import ScenarioPage from '@/pages/ScenarioPage';
import LoginPage from '@/modules/auth/LoginPage';
import SignupPage from '@/modules/auth/SignupPage';
import FindIdPage from '@/modules/auth/FindIdPage';
import FindPasswordPage from '@/modules/auth/FindPasswordPage';

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();
  if (isLoading) return <LoadingScreen />;
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function PublicRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();
  if (isLoading) return <LoadingScreen />;
  if (isAuthenticated) return <Navigate to="/" replace />;
  return <>{children}</>;
}

function LoadingScreen() {
  return (
    <div className="min-h-screen bg-surface flex items-center justify-center">
      <div className="text-center">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-primary text-white text-3xl mb-4 animate-pulse">
          🌱
        </div>
        <p className="text-gray-500">인증 확인 중...</p>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <ScenarioProvider>
          <Routes>
            {/* Public auth routes */}
            <Route path="/login" element={<PublicRoute><LoginPage /></PublicRoute>} />
            <Route path="/signup" element={<PublicRoute><SignupPage /></PublicRoute>} />
            <Route path="/find-id" element={<PublicRoute><FindIdPage /></PublicRoute>} />
            <Route path="/find-password" element={<PublicRoute><FindPasswordPage /></PublicRoute>} />

            {/* Protected app routes */}
            <Route element={<ProtectedRoute><AppLayout /></ProtectedRoute>}>
              <Route index element={<DashboardPage />} />
              <Route path="diagnosis" element={<DiagnosisPage />} />
              <Route path="iot" element={<IoTDashboardPage />} />
              <Route path="reviews" element={<ReviewsPage />} />
              <Route path="documents" element={<DocumentsPage />} />
              <Route path="weather" element={<WeatherPage />} />
              <Route path="harvest" element={<HarvestPage />} />
              <Route path="journal" element={<JournalPage />} />
              <Route path="market" element={<MarketPricePage />} />
              <Route path="scenario" element={<ScenarioPage />} />
            </Route>

            {/* Catch-all */}
            <Route path="*" element={<Navigate to="/login" replace />} />
          </Routes>
          <Toaster
            position="top-right"
            toastOptions={{
              duration: 4000,
              style: { fontSize: '16px', borderRadius: '12px' },
            }}
          >
            {(t) => (
              <ToastBar toast={t}>
                {({ icon, message }) => (
                  <>
                    {icon}
                    {message}
                    {t.type !== 'loading' && (
                      <button
                        onClick={() => toast.dismiss(t.id)}
                        className="ml-2 p-1 text-gray-400 hover:text-gray-700 cursor-pointer"
                        aria-label="닫기"
                      >
                        <MdClose className="text-base" />
                      </button>
                    )}
                  </>
                )}
              </ToastBar>
            )}
          </Toaster>
        </ScenarioProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}
