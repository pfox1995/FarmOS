import { useState } from 'react';

export default function ImageGallery({ images, name }: { images: string[]; name: string }) {
  const [selected, setSelected] = useState(0);
  const list = images.length > 0 ? images : ['https://picsum.photos/seed/default/600/600'];

  return (
    <div>
      <div className="aspect-square bg-gray-100 rounded-lg overflow-hidden mb-2">
        <img src={list[selected]} alt={name} className="w-full h-full object-cover" />
      </div>
      {list.length > 1 && (
        <div className="flex gap-2">
          {list.map((img, i) => (
            <button
              key={i}
              onClick={() => setSelected(i)}
              className={`w-16 h-16 rounded border-2 overflow-hidden ${i === selected ? 'border-[#03C75A]' : 'border-gray-200'}`}
            >
              <img src={img} alt="" className="w-full h-full object-cover" />
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
