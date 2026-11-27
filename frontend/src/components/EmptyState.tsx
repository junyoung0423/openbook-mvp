import type { ReactNode } from "react";

// 빈 상태: 안내 문장 + 다음 행동 버튼 1개
export function EmptyState({ message, action }: { message: ReactNode; action?: ReactNode }) {
  return (
    <div className="space-y-4 rounded-card border border-dashed border-line bg-surface p-6 text-center">
      <p>{message}</p>
      {action && <div className="flex justify-center">{action}</div>}
    </div>
  );
}
