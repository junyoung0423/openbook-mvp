import type { ReactNode } from "react";

export function Spinner({ className = "" }: { className?: string }) {
  return (
    <span
      aria-hidden
      className={`inline-block size-4 shrink-0 animate-spin rounded-full border-2 border-line border-t-brand motion-reduce:animate-none ${className}`}
    />
  );
}

// 처리 중 표시: 지금 하는 일 한 문장 + 걸리는 시간 안내
export function ProcessingState({ children, hint }: { children: ReactNode; hint?: ReactNode }) {
  return (
    <div role="status" className="flex items-start gap-3 rounded-control border border-line bg-surface p-4">
      <Spinner className="mt-1.5" />
      <div>
        <p>{children}</p>
        {hint && <p className="mt-1 text-small text-muted">{hint}</p>}
      </div>
    </div>
  );
}
