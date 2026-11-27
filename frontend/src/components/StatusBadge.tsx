import type { Term } from "../lib/api";

const LABEL: Record<Term["status"], string> = {
  extracted: "추출됨",
  not_found: "찾지 못함",
  user_input: "직접 입력",
};

// 색이 아니라 모양으로 구분한다: 추출됨 = 옅은 회색 채움, 찾지 못함 = 점선 테두리, 직접 입력 = 실선 테두리.
// 글자는 모두 잉크색이고, 안심하게 보이는 체크 표시는 쓰지 않는다.
const SHAPE: Record<Term["status"], string> = {
  extracted: "border border-transparent bg-line/60",
  not_found: "border border-dashed border-ink/60",
  user_input: "border border-solid border-ink/60",
};

export function StatusBadge({ status }: { status: Term["status"] }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-small font-medium text-ink ${SHAPE[status]}`}>
      {LABEL[status]}
    </span>
  );
}
