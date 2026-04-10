// Design Ref: §6.2 — RAGSearchPanel 컴포넌트
import { useState } from 'react';
import { MdSearch, MdFilterList } from 'react-icons/md';
import type { SearchResult } from '@/types';

interface Props {
  onSearch: (query: string, topK: number, filters?: { platform?: string; rating_min?: number; rating_max?: number }) => Promise<SearchResult[]>;
  results: SearchResult[];
  isSearching: boolean;
}

export default function RAGSearchPanel({ onSearch, results, isSearching }: Props) {
  const [query, setQuery] = useState('');
  const [showFilters, setShowFilters] = useState(false);
  const [platform, setPlatform] = useState('');
  const [ratingMax, setRatingMax] = useState<number | ''>('');
  const [dateFrom, setDateFrom] = useState('');

  const handleSearch = () => {
    if (!query.trim()) return;
    const filters: Record<string, unknown> = {};
    if (platform) filters.platform = platform;
    if (ratingMax) filters.rating_max = Number(ratingMax);
    if (dateFrom) filters.date_from = dateFrom;
    onSearch(query, 10, Object.keys(filters).length > 0 ? filters as { platform?: string; rating_max?: number } : undefined);
  };

  return (
    <div className="card">
      <div className="flex items-center gap-2 mb-4">
        <MdSearch className="text-xl text-primary" />
        <h3 className="section-title">RAG 의미 검색</h3>
      </div>

      <div className="flex gap-2 mb-3">
        <input
          type="text"
          value={query}
          onChange={e => setQuery(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleSearch()}
          placeholder="자연어로 리뷰 검색 (예: 포장 관련 불만)"
          className="flex-1 px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary"
        />
        <button
          onClick={() => setShowFilters(!showFilters)}
          className={`p-2 rounded-lg border ${showFilters ? 'border-primary text-primary bg-primary/5' : 'border-gray-200 text-gray-500'}`}
        >
          <MdFilterList className="text-lg" />
        </button>
        <button
          onClick={handleSearch}
          disabled={isSearching || !query.trim()}
          className="px-4 py-2 bg-primary text-white rounded-lg text-sm font-medium disabled:opacity-50 hover:bg-primary/90 transition-colors"
        >
          {isSearching ? '...' : '검색'}
        </button>
      </div>

      {showFilters && (
        <div className="flex gap-3 mb-3 p-3 bg-gray-50 rounded-lg">
          <select
            value={platform}
            onChange={e => setPlatform(e.target.value)}
            className="px-2 py-1.5 border border-gray-200 rounded text-sm"
          >
            <option value="">전체 플랫폼</option>
            <option value="네이버스마트스토어">네이버</option>
            <option value="쿠팡">쿠팡</option>
          </select>
          <select
            value={ratingMax}
            onChange={e => setRatingMax(e.target.value ? Number(e.target.value) : '')}
            className="px-2 py-1.5 border border-gray-200 rounded text-sm"
          >
            <option value="">평점 필터</option>
            <option value="3">3점 이하</option>
            <option value="2">2점 이하</option>
            <option value="1">1점만</option>
          </select>
          <input
            type="date"
            value={dateFrom}
            onChange={e => setDateFrom(e.target.value)}
            className="px-2 py-1.5 border border-gray-200 rounded text-sm"
            placeholder="시작 날짜"
          />
        </div>
      )}

      {results.length > 0 && (
        <div className="space-y-2 max-h-[300px] overflow-y-auto">
          {results.map((r, i) => (
            <div key={r.id} className="flex items-start gap-3 p-3 rounded-xl bg-gray-50">
              <span className="mt-0.5 text-xs font-mono text-gray-400 w-6 text-right flex-shrink-0">
                {(r.similarity * 100).toFixed(0)}%
              </span>
              <div className="flex-1 min-w-0">
                <p className="text-sm text-gray-800">{r.text}</p>
                <div className="flex items-center gap-2 mt-1">
                  <span className="text-xs text-gray-400">
                    {(r.metadata as { platform?: string })?.platform || ''}
                  </span>
                  <span className="text-xs text-amber-500">
                    {'★'.repeat((r.metadata as { rating?: number })?.rating || 0)}
                  </span>
                </div>
              </div>
            </div>
          ))}
          <p className="text-xs text-gray-400 text-center">{results.length}건 검색됨</p>
        </div>
      )}

      {results.length === 0 && query && !isSearching && (
        <p className="text-sm text-gray-400 text-center py-4">검색 결과가 없습니다</p>
      )}
    </div>
  );
}
