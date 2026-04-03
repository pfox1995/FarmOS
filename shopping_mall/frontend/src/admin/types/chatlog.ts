export interface ChatLog {
  id: number;
  user_id: number;
  intent: string;
  question: string;
  answer: string;
  escalated: boolean;
  created_at: string;
}
