import Banner from '@/components/home/Banner';
import CategoryNav from '@/components/common/CategoryNav';
import RecommendSection from '@/components/home/RecommendSection';
import PopularSection from '@/components/home/PopularSection';

export default function HomePage() {
  return (
    <div>
      <CategoryNav />
      <Banner />
      <RecommendSection />
      <PopularSection />
    </div>
  );
}
