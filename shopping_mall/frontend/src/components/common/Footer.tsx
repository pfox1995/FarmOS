export default function Footer() {
  return (
    <footer className="bg-gray-100 border-t border-gray-200 mt-8">
      <div className="max-w-6xl mx-auto px-4 py-8 text-sm text-gray-500">
        <div className="flex gap-4 mb-4">
          <span>고객센터</span>
          <span>이용약관</span>
          <span>개인정보처리방침</span>
        </div>
        <p>FarmOS 마켓 | 대표: 홍길동 | 사업자등록번호: 123-45-67890</p>
        <p className="mt-1">주소: 서울특별시 강남구 테헤란로 123 | 전화: 02-1234-5678</p>
        <p className="mt-2 text-gray-400">&copy; 2026 FarmOS Market. All rights reserved. (더미 데이터)</p>
      </div>
    </footer>
  );
}
