"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useContract } from "./ShellContext";

export const CONTRACT_PATHS = ["/terms", "/statements", "/results", "/qa"];

const TABS = [
  { path: "/terms", label: "조건 확인", short: "조건" },
  { path: "/statements", label: "정산서 입력", short: "정산서" },
  { path: "/results", label: "대조 결과", short: "결과" },
  { path: "/qa", label: "질문하기", short: "질문" },
];

// 계약서 화면 맨 위: 계약서 이름 + 탭 4개. 계약서 상태가 `확정`이 아니면 정산서 입력·대조 결과 탭은 흐리게 둔다
// (링크는 막지 않는다: 결과 화면이 TERMS_NOT_CONFIRMED를 이미 처리한다).
export function ContractHeader({ contractId }: { contractId: string }) {
  const pathname = usePathname();
  const { contract } = useContract();
  const locked = contract !== null && contract.status !== "확정";

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-1.5">
        {contract && <p className="num text-small text-muted">올린 날짜 {contract.uploaded_at.slice(0, 10)}</p>}
        <h1 className="break-words text-[22px] font-[750] tracking-heading md:text-name">{contract?.title ?? "계약서"}</h1>
      </div>
      <nav
        aria-label="계약서 메뉴"
        className="grid grid-cols-4 gap-0.5 rounded-tabbar bg-tabbar p-1 text-[13px] font-semibold md:inline-flex md:self-start md:text-sm"
      >
        {TABS.map((t) => {
          const current = pathname === t.path;
          const dim = locked && (t.path === "/statements" || t.path === "/results");
          return (
            <Link
              key={t.path}
              href={`${t.path}?id=${contractId}`}
              aria-current={current ? "page" : undefined}
              aria-label={t.label}
              title={dim ? "조건을 확정하면 열립니다" : undefined}
              className={`flex min-h-11 items-center justify-center rounded-tab px-0 md:px-[18px] ${
                current ? "bg-card font-[750] text-accent shadow-tab" : dim ? "font-medium text-[#626779]" : "text-ink-2 hover:text-ink"
              }`}
            >
              <span aria-hidden className="md:hidden">
                {t.short}
              </span>
              <span aria-hidden className="hidden md:inline">
                {t.label}
              </span>
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
