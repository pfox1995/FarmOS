export interface Category {
  id: number;
  name: string;
  parentId: number | null;
  icon: string | null;
  sortOrder: number;
  children?: Category[];
}
