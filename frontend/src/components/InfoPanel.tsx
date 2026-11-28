import type { ReactNode } from "react";

// `계산 불가`, 처리 중 같은 안내. 노란색·빨간색 경고 박스가 아니라 테두리 있는 중립 박스.
export function InfoPanel({
  title,
  children,
  role,
  className = "",
}: {
  title?: ReactNode;
  children?: ReactNode;
  role?: "status" | "alert";
  className?: string;
}) {
  return (
    <div role={role} className={`space-y-2 rounded-card border border-ink-2/30 bg-card p-5 md:p-6 ${className}`}>
      {title && <p className="text-[17px] font-bold">{title}</p>}
      {children && <div className="text-[15px] leading-relaxed text-ink-2">{children}</div>}
    </div>
  );
}
