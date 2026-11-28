import type { ReactNode } from "react";

// 빈 상태: 안내 문장 + 다음 행동 버튼 1개
export function EmptyState({ message, action }: { message: ReactNode; action?: ReactNode }) {
  return (
    <div className="space-y-4 rounded-card bg-card p-8 text-center shadow-card">
      <p className="text-ink-2">{message}</p>
      {action && <div className="flex justify-center">{action}</div>}
    </div>
  );
}
