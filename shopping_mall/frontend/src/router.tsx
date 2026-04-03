import { createBrowserRouter } from 'react-router-dom';
import App from './App';
import HomePage from '@/pages/HomePage';
import ProductListPage from '@/pages/ProductListPage';
import ProductDetailPage from '@/pages/ProductDetailPage';
import SearchPage from '@/pages/SearchPage';
import CartPage from '@/pages/CartPage';
import OrderPage from '@/pages/OrderPage';
import OrderCompletePage from '@/pages/OrderCompletePage';
import MyPage from '@/pages/MyPage';
import MyOrdersPage from '@/pages/MyOrdersPage';
import WishlistPage from '@/pages/WishlistPage';
import StorePage from '@/pages/StorePage';

import AdminLayout from '@/admin/AdminLayout';
import DashboardPage from '@/admin/pages/DashboardPage';
import ChatbotPage from '@/admin/pages/ChatbotPage';
import CalendarPage from '@/admin/pages/CalendarPage';
import ShipmentsPage from '@/admin/pages/ShipmentsPage';
import ReportsPage from '@/admin/pages/ReportsPage';
import AnalyticsPage from '@/admin/pages/AnalyticsPage';
import ExpensesPage from '@/admin/pages/ExpensesPage';

export const router = createBrowserRouter([
  {
    path: '/',
    element: <App />,
    children: [
      { index: true, element: <HomePage /> },
      { path: 'products', element: <ProductListPage /> },
      { path: 'products/:id', element: <ProductDetailPage /> },
      { path: 'search', element: <SearchPage /> },
      { path: 'cart', element: <CartPage /> },
      { path: 'order', element: <OrderPage /> },
      { path: 'order/complete', element: <OrderCompletePage /> },
      { path: 'mypage', element: <MyPage /> },
      { path: 'mypage/orders', element: <MyOrdersPage /> },
      { path: 'mypage/wishlist', element: <WishlistPage /> },
      { path: 'store/:id', element: <StorePage /> },
    ],
  },
  {
    path: '/admin',
    element: <AdminLayout />,
    children: [
      { index: true, element: <DashboardPage /> },
      { path: 'chatbot', element: <ChatbotPage /> },
      { path: 'calendar', element: <CalendarPage /> },
      { path: 'shipments', element: <ShipmentsPage /> },
      { path: 'reports', element: <ReportsPage /> },
      { path: 'analytics', element: <AnalyticsPage /> },
      { path: 'expenses', element: <ExpensesPage /> },
    ],
  },
]);
