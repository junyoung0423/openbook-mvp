// NEXT_PUBLIC_DEMO_MODE=1로 빌드하면 모든 화면 맨 위에 "데모 버전" 띠가 나온다 (빌드 때 정해지는 값).
// 판단을 암시하는 노랑·빨강 대신 중립 색을 쓴다.
const DEMO_MODE = process.env.NEXT_PUBLIC_DEMO_MODE === "1";

export function DemoBanner() {
  if (!DEMO_MODE) return null;
  return (
    <div role="note" className="border-b border-line bg-card px-4 py-2 text-center text-small text-ink-2">
      <strong className="font-bold text-ink">데모 버전</strong> · 화면의 계약서·정산서는 모두 가상 데이터입니다.
    </div>
  );
}
