import { useState, useEffect, useMemo } from 'react';
import { MdTrendingUp, MdTrendingDown, MdShowChart, MdWarningAmber } from 'react-icons/md';
import { useMarketData } from '@/hooks/useMarketData';
import type { KamisItemPrice, ImportantChange } from '@/types';

// ── 가격 문자열 파싱 ───────────────────────────────────
function parseKamisPrice(raw: unknown): number | null {
  if (raw == null) return null;
  if (typeof raw === 'number') return raw;
  if (typeof raw !== 'string') return null;
  if (!raw || raw === '-' || raw.trim() === '') return null;
  const num = parseInt(raw.replace(/,/g, ''), 10);
  return Number.isNaN(num) ? null : num;
}

// ── 주요 변동 감지 임계값 ──────────────────────────────
const DAILY_CHANGE_THRESHOLD = 5;   // %
const WEEKLY_CHANGE_THRESHOLD = 10; // %

function detectImportantChanges(items: KamisItemPrice[]): ImportantChange[] {
  const changes: ImportantChange[] = [];

  for (const item of items) {
    const current = parseKamisPrice(item.dpr1);
    const yesterday = parseKamisPrice(item.dpr2);
    const weekAgo = parseKamisPrice(item.dpr3);

    if (current == null || current === 0) continue;

    let isImportant = false;
    let changePercent = 0;
    let previousPrice = 0;

    // 전일 대비 변동
    if (yesterday != null && yesterday !== 0) {
      changePercent = ((current - yesterday) / yesterday) * 100;
      previousPrice = yesterday;
      if (Math.abs(changePercent) >= DAILY_CHANGE_THRESHOLD) {
        isImportant = true;
      }
    }

    // 1주일 전 대비 변동
    if (!isImportant && weekAgo != null && weekAgo !== 0) {
      const weekChange = ((current - weekAgo) / weekAgo) * 100;
      if (Math.abs(weekChange) >= WEEKLY_CHANGE_THRESHOLD) {
        isImportant = true;
        changePercent = weekChange;
        previousPrice = weekAgo;
      }
    }

    if (isImportant) {
      changes.push({
        item_name: item.item_name,
        productno: item.productno,
        category_name: item.category_name,
        unit: item.unit,
        currentPrice: current,
        previousPrice,
        changePercent,
        direction: changePercent > 0 ? 'up' : 'down',
      });
    }
  }

  return changes.sort((a, b) => Math.abs(b.changePercent) - Math.abs(a.changePercent));
}

export default function MarketPricePage() {
  const { latestPrices, loading, error, fetchLatest } = useMarketData();
  const [productCls, setProductCls] = useState<'' | '01' | '02'>('01');
  const [categoryFilter, setCategoryFilter] = useState<string>('');

  useEffect(() => { fetchLatest(productCls); }, [fetchLatest, productCls]);

  const importantChanges = useMemo(() => detectImportantChanges(latestPrices), [latestPrices]);

  // 부류별 카테고리 목록 추출
  const categories = useMemo(() => {
    const map = new Map<string, string>();
    for (const item of latestPrices) {
      if (item.category_code && item.category_name) {
        map.set(item.category_code, item.category_name);
      }
    }
    return Array.from(map.entries());
  }, [latestPrices]);

  // 필터링된 가격 목록
  const filteredPrices = useMemo(() => {
    if (!categoryFilter) return latestPrices;
    return latestPrices.filter(item => item.category_code === categoryFilter);
  }, [latestPrices, categoryFilter]);

  // ── 로딩 / 에러 ────────────────────────────────────────
  if (loading && latestPrices.length === 0) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-primary/10 text-primary text-2xl mb-3 animate-pulse">
            <MdShowChart />
          </div>
          <p className="text-gray-500">시세 정보를 불러오는 중...</p>
        </div>
      </div>
    );
  }

  if (error && latestPrices.length === 0) {
    return (
      <div className="card bg-red-50 border-red-200">
        <div className="flex items-center gap-3">
          <MdWarningAmber className="text-2xl text-danger" />
          <div>
            <p className="font-semibold text-gray-900">시세 정보를 불러올 수 없습니다</p>
            <p className="text-sm text-gray-600 mt-1">{error}</p>
          </div>
        </div>
        <button onClick={() => fetchLatest(productCls)} className="btn-primary mt-4 text-sm">
          다시 시도
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* ── 소매/도매 토글 ─────────────────────────────── */}
      <div className="flex items-center gap-2">
        {([['01', '소매가격'], ['02', '도매가격']] as const).map(([code, label]) => (
          <button
            key={code}
            onClick={() => setProductCls(code)}
            className={`px-4 py-2 rounded-xl text-sm font-medium transition ${
              productCls === code
                ? 'bg-primary text-white'
                : 'bg-white text-gray-600 border border-gray-200 hover:bg-gray-50'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* ── 주요 가격 변동 알림 ──────────────────────── */}
      <div className={`card ${importantChanges.length > 0 ? 'bg-gradient-to-r from-amber-50 to-orange-50 border-amber-200' : 'bg-gradient-to-r from-green-50 to-emerald-50 border-green-200'}`}>
        <div className="flex items-center gap-2 mb-3">
          <MdWarningAmber className={`text-xl ${importantChanges.length > 0 ? 'text-amber-500' : 'text-success'}`} />
          <h3 className="section-title">주요 가격 변동</h3>
          <span className="text-xs text-gray-400 ml-auto">전일 대비 {DAILY_CHANGE_THRESHOLD}% 이상 또는 전주 대비 {WEEKLY_CHANGE_THRESHOLD}% 이상</span>
        </div>

        {importantChanges.length === 0 ? (
          <p className="text-sm text-gray-600">오늘은 큰 가격 변동이 없습니다.</p>
        ) : (
          <div className="space-y-2">
            {importantChanges.slice(0, 10).map((c, i) => (
              <div key={i} className="flex items-center justify-between p-3 bg-white/70 rounded-xl">
                <div className="flex items-center gap-2">
                  {c.direction === 'up'
                    ? <MdTrendingUp className="text-lg text-danger" />
                    : <MdTrendingDown className="text-lg text-success" />}
                  <span className="font-medium text-gray-800">{c.item_name}</span>
                  <span className="text-xs text-gray-400">{c.category_name}</span>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-sm text-gray-500">
                    {c.previousPrice.toLocaleString()} → {c.currentPrice.toLocaleString()}원/{c.unit}
                  </span>
                  <span className={`badge ${c.direction === 'up' ? 'badge-danger' : 'badge-success'}`}>
                    {c.direction === 'up' ? '+' : ''}{c.changePercent.toFixed(1)}%
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ── 부류 필터 ────────────────────────────────── */}
      <div className="flex flex-wrap items-center gap-2">
        <button
          onClick={() => setCategoryFilter('')}
          className={`px-3 py-1.5 rounded-lg text-sm transition ${
            !categoryFilter ? 'bg-primary text-white' : 'bg-white text-gray-600 border border-gray-200 hover:bg-gray-50'
          }`}
        >
          전체
        </button>
        {categories.map(([code, name]) => (
          <button
            key={code}
            onClick={() => setCategoryFilter(code)}
            className={`px-3 py-1.5 rounded-lg text-sm transition ${
              categoryFilter === code ? 'bg-primary text-white' : 'bg-white text-gray-600 border border-gray-200 hover:bg-gray-50'
            }`}
          >
            {name}
          </button>
        ))}
      </div>

      {/* ── 가격 목록 테이블 ─────────────────────────── */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h3 className="section-title">
            {productCls === '01' ? '소매' : '도매'} 가격 현황
          </h3>
          <span className="text-xs text-gray-400">{filteredPrices.length}개 품목</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="text-left py-3 px-4 font-semibold text-gray-600">품목</th>
                <th className="text-center py-3 px-4 font-semibold text-gray-600">단위</th>
                <th className="text-right py-3 px-4 font-semibold text-gray-600">당일</th>
                <th className="text-right py-3 px-4 font-semibold text-gray-600">1일전</th>
                <th className="text-right py-3 px-4 font-semibold text-gray-600">1주전</th>
                <th className="text-right py-3 px-4 font-semibold text-gray-600">1개월전</th>
                <th className="text-center py-3 px-4 font-semibold text-gray-600">등락</th>
              </tr>
            </thead>
            <tbody>
              {filteredPrices.map((item, idx) => {
                const cur = parseKamisPrice(item.dpr1);
                const prev = parseKamisPrice(item.dpr2);
                const diff = cur != null && prev != null && prev !== 0
                  ? ((cur - prev) / prev * 100)
                  : null;

                return (
                  <tr key={idx} className="border-b border-gray-50 hover:bg-gray-50 transition-colors">
                    <td className="py-3 px-4">
                      <span className="font-medium">{item.item_name}</span>
                    </td>
                    <td className="text-center py-3 px-4 text-gray-400">{item.unit}</td>
                    <td className="text-right py-3 px-4 font-semibold">
                      {item.dpr1 || '-'}
                    </td>
                    <td className="text-right py-3 px-4 text-gray-500">{item.dpr2 || '-'}</td>
                    <td className="text-right py-3 px-4 text-gray-500">{item.dpr3 || '-'}</td>
                    <td className="text-right py-3 px-4 text-gray-500">{item.dpr4 || '-'}</td>
                    <td className="text-center py-3 px-4">
                      {diff != null ? (
                        <span className={`inline-flex items-center gap-0.5 text-xs font-medium ${
                          diff > 0 ? 'text-danger' : diff < 0 ? 'text-success' : 'text-gray-400'
                        }`}>
                          {diff > 0 ? <MdTrendingUp /> : diff < 0 ? <MdTrendingDown /> : null}
                          {diff > 0 ? '+' : ''}{diff.toFixed(1)}%
                        </span>
                      ) : (
                        <span className="text-gray-300">-</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        {filteredPrices.length === 0 && !loading && (
          <p className="text-sm text-gray-400 text-center py-8">가격 데이터가 없습니다.</p>
        )}
      </div>
    </div>
  );
}
