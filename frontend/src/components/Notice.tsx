import type { ReactNode } from "react";

// 고정 안내(회색 작은 글씨 박스)
export function Notice({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <aside className={`rounded-tile bg-quote px-4 py-3 text-small leading-relaxed text-muted ${className}`}>{children}</aside>;
}
