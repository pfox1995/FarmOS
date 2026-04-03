import { format } from 'date-fns';
import { ko } from 'date-fns/locale';

export function formatPrice(price: number): string {
  return new Intl.NumberFormat('ko-KR', {
    style: 'currency',
    currency: 'KRW',
    maximumFractionDigits: 0,
  }).format(price);
}

export function getDiscountedPrice(price: number, discountRate: number): number {
  return Math.floor(price * (1 - discountRate / 100));
}

export function formatDate(date: string | Date, pattern = 'yyyy-MM-dd HH:mm'): string {
  return format(new Date(date), pattern, { locale: ko });
}

export function truncate(str: string, length: number): string {
  if (str.length <= length) return str;
  return str.slice(0, length) + '...';
}
