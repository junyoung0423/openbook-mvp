import { Loader } from "lucide-react";
import type { ReactNode } from "react";

// 완전한 원 모양 금지 규칙에 맞춰 CSS 원 대신 살이 있는 아이콘을 돌린다
export function Spinner({ className = "" }: { className?: string }) {
  return <Loader aria-hidden size={18} className={`shrink-0 animate-spin text-accent motion-reduce:animate-none ${className}`} />;
}

// 처리 중 표시: 지금 하는 일 한 문장 + 걸리는 시간 안내
export function ProcessingState({ children, hint }: { children: ReactNode; hint?: ReactNode }) {
  return (
    <div role="status" className="flex items-start gap-3 rounded-card bg-card p-4 shadow-card">
      <Spinner className="mt-1" />
      <div>
        <p>{children}</p>
        {hint && <p className="mt-1 text-[14px] text-ink-2">{hint}</p>}
      </div>
    </div>
  );
}
