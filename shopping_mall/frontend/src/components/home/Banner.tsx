import { useState, useEffect } from 'react';

const slides = [
  { bg: 'from-green-400 to-green-600', title: '신선한 농산물 직거래', sub: '산지에서 바로 식탁까지' },
  { bg: 'from-orange-400 to-red-500', title: '산지 직송 특가', sub: '최대 30% 할인' },
  { bg: 'from-blue-400 to-indigo-500', title: '첫 주문 10% 할인', sub: '지금 바로 시작하세요' },
];

export default function Banner() {
  const [current, setCurrent] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => setCurrent((p) => (p + 1) % slides.length), 4000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="relative overflow-hidden rounded-xl mx-4 mt-4 h-48 md:h-64">
      {slides.map((s, i) => (
        <div
          key={i}
          className={`absolute inset-0 bg-gradient-to-r ${s.bg} flex flex-col items-center justify-center text-white transition-opacity duration-700 ${i === current ? 'opacity-100' : 'opacity-0'}`}
        >
          <h2 className="text-2xl md:text-4xl font-bold">{s.title}</h2>
          <p className="mt-2 text-lg">{s.sub}</p>
        </div>
      ))}
      <div className="absolute bottom-4 left-1/2 -translate-x-1/2 flex gap-2">
        {slides.map((_, i) => (
          <button
            key={i}
            onClick={() => setCurrent(i)}
            className={`w-2 h-2 rounded-full ${i === current ? 'bg-white' : 'bg-white/50'}`}
          />
        ))}
      </div>
    </div>
  );
}
