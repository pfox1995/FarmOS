import type { ProductOption } from '@/types/product';
import QuantitySelector from '@/components/common/QuantitySelector';

interface Props {
  options: ProductOption[];
  selectedOptions: Record<string, string>;
  onOptionChange: (name: string, value: string) => void;
  quantity: number;
  onQuantityChange: (q: number) => void;
  stock: number;
}

export default function OptionSelector({ options, selectedOptions, onOptionChange, quantity, onQuantityChange, stock }: Props) {
  return (
    <div className="space-y-3">
      {(options ?? []).map((opt) => (
        <div key={opt.name}>
          <label className="text-sm font-medium text-gray-700">{opt.name}</label>
          <select
            value={selectedOptions[opt.name] || ''}
            onChange={(e) => onOptionChange(opt.name, e.target.value)}
            className="mt-1 block w-full rounded border border-gray-300 px-3 py-2 text-sm"
          >
            <option value="">선택해주세요</option>
            {(opt.values ?? []).map((v) => (
              <option key={v} value={v}>{v}</option>
            ))}
          </select>
        </div>
      ))}
      <div>
        <label className="text-sm font-medium text-gray-700">수량</label>
        <div className="mt-1">
          <QuantitySelector quantity={quantity} onChange={onQuantityChange} max={stock} />
        </div>
      </div>
    </div>
  );
}
