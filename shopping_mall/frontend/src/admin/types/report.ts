export interface WeeklyReport {
  id: number;
  week_start: string;
  week_end: string;
  net_profit: number;
  content?: string;
  created_at: string;
}
