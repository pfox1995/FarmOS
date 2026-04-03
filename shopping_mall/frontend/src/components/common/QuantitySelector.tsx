interface Props {
  quantity: number;
  onChange: (q: number) => void;
  min?: number;
  max?: number;
}

export default function QuantitySelector({ quantity, onChange, min = 1, max = 99 }: Props) {
  return (
    <div className="flex items-center border rounded">
      <button
        onClick={() => onChange(Math.max(min, quantity - 1))}
        className="w-8 h-8 text-lg hover:bg-gray-100"
      >
        -
      </button>
      <span className="w-10 text-center text-sm">{quantity}</span>
      <button
        onClick={() => onChange(Math.min(max, quantity + 1))}
        className="w-8 h-8 text-lg hover:bg-gray-100"
      >
        +
      </button>
    </div>
  );
}
