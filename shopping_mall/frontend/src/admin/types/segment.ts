export interface CustomerSegment {
  user_id: number;
  name: string;
  email: string;
  total_spent: number;
  order_count: number;
  segment: string;
}

export interface SegmentSummary {
  segment: string;
  count: number;
}
