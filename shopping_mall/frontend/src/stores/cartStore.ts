import { create } from 'zustand';

interface CartState {
  selectedIds: Set<number>;
  toggleSelect: (id: number) => void;
  selectAll: (ids: number[]) => void;
  deselectAll: () => void;
  isSelected: (id: number) => boolean;
}

export const useCartStore = create<CartState>((set, get) => ({
  selectedIds: new Set(),
  toggleSelect: (id) =>
    set((state) => {
      const next = new Set(state.selectedIds);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return { selectedIds: next };
    }),
  selectAll: (ids) => set({ selectedIds: new Set(ids) }),
  deselectAll: () => set({ selectedIds: new Set() }),
  isSelected: (id) => get().selectedIds.has(id),
}));
