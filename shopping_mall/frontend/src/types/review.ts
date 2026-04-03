export interface Review {
  id: number;
  productId: number;
  userId: number;
  rating: number;
  content: string | null;
  images: string[];
  createdAt: string;
  user: { id: number; name: string };
}

export interface ReviewListResponse {
  items: Review[];
  total: number;
  page: number;
  limit: number;
}
