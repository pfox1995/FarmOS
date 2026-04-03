interface Props {
  rating: number;
  size?: 'sm' | 'md' | 'lg';
}

export default function StarRating({ rating, size = 'md' }: Props) {
  const sizeClass = size === 'sm' ? 'text-xs' : size === 'lg' ? 'text-xl' : 'text-sm';
  const full = Math.floor(rating);
  const half = rating - full >= 0.5;

  return (
    <span className={sizeClass}>
      {'★'.repeat(full)}
      {half && '★'}
      {'☆'.repeat(5 - full - (half ? 1 : 0))}
    </span>
  );
}
