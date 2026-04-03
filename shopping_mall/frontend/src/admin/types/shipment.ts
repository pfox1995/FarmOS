export interface Shipment {
  id: number;
  order_id: number;
  carrier: string;
  tracking_number: string;
  status: string;
  last_checked: string;
  delivered_at: string | null;
  created_at: string;
}

export interface ShipmentCreatePayload {
  order_id: number;
  carrier: string;
  tracking_number: string;
}
