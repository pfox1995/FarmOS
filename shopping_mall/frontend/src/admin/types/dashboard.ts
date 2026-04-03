export interface DashboardData {
  today_revenue: number;
  today_orders: number;
  new_customers: number;
  revenue_change: number;
  orders_change: number;
  customers_change: number;
  weekly_revenue: { date: string; revenue: number }[];
  segments: { name: string; count: number }[];
}
