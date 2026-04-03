import type { ShippingAddress } from '@/types/order';

interface Props {
  address: ShippingAddress;
  onChange: (addr: ShippingAddress) => void;
}

export default function OrderForm({ address, onChange }: Props) {
  const update = (field: keyof ShippingAddress, value: string) =>
    onChange({ ...address, [field]: value });

  return (
    <div className="bg-white rounded-lg border p-6">
      <h3 className="font-bold text-lg mb-4">배송 정보</h3>
      <div className="space-y-3">
        <div>
          <label className="text-sm text-gray-600">받는 분</label>
          <input value={address.recipient} onChange={(e) => update('recipient', e.target.value)} className="mt-1 block w-full rounded border px-3 py-2 text-sm" />
        </div>
        <div>
          <label className="text-sm text-gray-600">연락처</label>
          <input value={address.phone} onChange={(e) => update('phone', e.target.value)} placeholder="010-0000-0000" className="mt-1 block w-full rounded border px-3 py-2 text-sm" />
        </div>
        <div>
          <label className="text-sm text-gray-600">우편번호</label>
          <input value={address.zipCode} onChange={(e) => update('zipCode', e.target.value)} className="mt-1 block w-full rounded border px-3 py-2 text-sm" />
        </div>
        <div>
          <label className="text-sm text-gray-600">주소</label>
          <input value={address.address} onChange={(e) => update('address', e.target.value)} className="mt-1 block w-full rounded border px-3 py-2 text-sm" />
        </div>
        <div>
          <label className="text-sm text-gray-600">상세주소</label>
          <input value={address.detail} onChange={(e) => update('detail', e.target.value)} className="mt-1 block w-full rounded border px-3 py-2 text-sm" />
        </div>
      </div>
    </div>
  );
}
