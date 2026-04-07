import { useState, useCallback } from 'react';
import type { KamisItemPrice } from '@/types';

const API_BASE = 'http://localhost:8000/api/v1';

interface MarketData {
  latestPrices: KamisItemPrice[];
  loading: boolean;
  error: string | null;
}

export function useMarketData() {
  const [data, setData] = useState<MarketData>({
    latestPrices: [],
    loading: false,
    error: null,
  });

  const fetchLatest = useCallback(async (productClsCode = '') => {
    setData(prev => ({ ...prev, loading: true, error: null }));
    try {
      const params = new URLSearchParams();
      if (productClsCode) params.set('product_cls_code', productClsCode);
      const res = await fetch(
        `${API_BASE}/market/latest?${params}`,
        { credentials: 'include' },
      );
      if (!res.ok) throw new Error(`${res.status}`);
      const json = await res.json();
      setData(prev => ({ ...prev, latestPrices: json.items ?? [], loading: false }));
    } catch (err) {
      setData(prev => ({
        ...prev,
        loading: false,
        error: err instanceof Error ? err.message : '시세 정보를 불러올 수 없습니다.',
      }));
    }
  }, []);

  return { ...data, fetchLatest };
}
