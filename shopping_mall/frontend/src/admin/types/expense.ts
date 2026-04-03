export interface ExpenseEntry {
  id: number;
  date: string;
  description: string;
  amount: number;
  category: string | null;
  auto_classified: boolean;
  created_at: string;
}

export interface ExpenseCreatePayload {
  date: string;
  description: string;
  amount: number;
  category?: string;
}
