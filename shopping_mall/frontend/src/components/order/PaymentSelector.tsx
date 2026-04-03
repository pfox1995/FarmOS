const methods = ['신용카드', '무통장입금', '카카오페이', '네이버페이'];

interface Props {
  selected: string;
  onChange: (method: string) => void;
}

export default function PaymentSelector({ selected, onChange }: Props) {
  return (
    <div className="bg-white rounded-lg border p-6">
      <h3 className="font-bold text-lg mb-4">결제 수단</h3>
      <div className="space-y-2">
        {methods.map((m) => (
          <label key={m} className="flex items-center gap-2 cursor-pointer">
            <input type="radio" name="payment" checked={selected === m} onChange={() => onChange(m)} className="accent-[#03C75A]" />
            <span className="text-sm">{m}</span>
          </label>
        ))}
      </div>
    </div>
  );
}
