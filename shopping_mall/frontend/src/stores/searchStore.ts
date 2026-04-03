import { create } from 'zustand';

interface SearchState {
  keyword: string;
  recentSearches: string[];
  setKeyword: (keyword: string) => void;
  addRecentSearch: (keyword: string) => void;
  clearRecentSearches: () => void;
}

export const useSearchStore = create<SearchState>((set) => ({
  keyword: '',
  recentSearches: [],
  setKeyword: (keyword) => set({ keyword }),
  addRecentSearch: (keyword) =>
    set((state) => ({
      recentSearches: [keyword, ...state.recentSearches.filter((k) => k !== keyword)].slice(0, 10),
    })),
  clearRecentSearches: () => set({ recentSearches: [] }),
}));
