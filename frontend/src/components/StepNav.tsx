"use client";

import Link from "next/link";
import { useState } from "react";

export type Step = "terms" | "statements" | "results" | "qa";

const STEPS = [
  { key: "contract", label: "계약서", path: "/" },
  { key: "terms", label: "조건 확인", path: "/terms" },
  { key: "statements", label: "정산서 입력", path: "/statements" },
  { key: "results", label: "대조 결과", path: "/results" },
] as const;

// 계약서 id가 있는 화면 위쪽의 단계 표시. 계약서 상태가 `확정`이 아니면 ③④를 회색으로 두고 안내만 붙인다(링크는 막지 않는다:
// 결과 화면이 TERMS_NOT_CONFIRMED를 이미 처리한다).
export function StepNav({ contractId, step, status }: { contractId: string; step: Step; status: string | null }) {
  const [open, setOpen] = useState(false);
  const locked = status !== null && status !== "확정";
  const href = (path: string) => (path === "/" ? "/" : `${path}?id=${contractId}`);
  const index = STEPS.findIndex((s) => s.key === step);
  const summary = index >= 0 ? `${index + 1} / ${STEPS.length} ${STEPS[index].label}` : "계약서에 질문하기";

  const linkBase =
    "flex min-h-11 items-center gap-2 rounded-control px-3 text-small focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand";

  return (
    <nav aria-label="진행 단계" className="mb-4">
      <button
        type="button"
        aria-expanded={open}
        aria-controls="step-list"
        onClick={() => setOpen((v) => !v)}
        className="flex min-h-11 w-full items-center justify-between rounded-control border border-line bg-surface px-4 text-left font-medium sm:hidden"
      >
        <span className="num">{summary}</span>
        <span aria-hidden className="text-muted">
          {open ? "접기" : "단계 보기"}
        </span>
      </button>

      <div id="step-list" className={`${open ? "mt-2 flex" : "hidden"} flex-col gap-1 sm:mt-0 sm:flex sm:flex-row sm:items-center`}>
        <ol className="flex flex-col gap-1 sm:flex-1 sm:flex-row sm:items-center">
          {STEPS.map((s, i) => {
            const current = s.key === step;
            const dim = locked && (s.key === "statements" || s.key === "results");
            return (
              <li key={s.key} className="sm:flex-1">
                <Link
                  href={href(s.path)}
                  aria-current={current ? "step" : undefined}
                  className={`${linkBase} ${
                    current ? "bg-brand-soft font-semibold text-brand" : dim ? "text-muted" : "text-ink hover:bg-paper"
                  }`}
                >
                  <span
                    aria-hidden
                    className={`num flex size-6 shrink-0 items-center justify-center rounded-full border text-fine ${
                      current ? "border-brand bg-brand text-white" : "border-line"
                    }`}
                  >
                    {i + 1}
                  </span>
                  {s.label}
                </Link>
              </li>
            );
          })}
        </ol>
        <Link
          href={`/qa?id=${contractId}`}
          aria-current={step === "qa" ? "step" : undefined}
          className={`${linkBase} whitespace-nowrap underline underline-offset-2 ${
            step === "qa" ? "bg-brand-soft font-semibold text-brand" : "text-brand"
          }`}
        >
          계약서에 질문하기
        </Link>
      </div>
      {locked && <p className="mt-1 px-3 text-fine text-muted">조건을 확정하면 정산서 입력과 대조 결과가 열립니다.</p>}
    </nav>
  );
}
