export interface Store {
  id: number;
  name: string;
  description: string | null;
  imageUrl: string | null;
  rating: number;
  productCount: number;
}
