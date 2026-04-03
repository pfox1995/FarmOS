import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSearchStore } from '@/stores/searchStore';

export default function SearchBar() {
  const navigate = useNavigate();
  const { addRecentSearch } = useSearchStore();
  const [value, setValue] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const q = value.trim();
    if (!q) return;
    addRecentSearch(q);
    navigate(`/search?q=${encodeURIComponent(q)}`);
    setValue('');
  };

  return (
    <form onSubmit={handleSubmit} className="relative">
      <input
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="상품을 검색해보세요"
        className="w-full h-10 pl-4 pr-10 rounded-full border-2 border-[#03C75A] text-sm outline-none focus:shadow-md"
      />
      <button type="submit" className="absolute right-3 top-1/2 -translate-y-1/2 text-[#03C75A] font-bold">
        검색
      </button>
    </form>
  );
}
