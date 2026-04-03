export interface HarvestSchedule {
  id: number;
  product_name: string;
  harvest_date: string;
  estimated_quantity: number;
  notes?: string;
  created_at: string;
}

export interface HarvestCreatePayload {
  product_name: string;
  harvest_date: string;
  estimated_quantity: number;
  notes?: string;
}
