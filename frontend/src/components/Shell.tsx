"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, type ReactNode } from "react";

// 모든 화면이 같이 쓰는 틀: 위쪽 머리(로고·단계), 데모 띠, 가운데 본문, 아래 안내.

export type Step = "upload" | "terms" | "statements" | "results" | "qa";

const STEPS: { key: Step; label: string; path: string }[] = [
  { key: "upload", label: "계약서", path: "/" },
  { key: "terms", label: "조건 확인", path: "/terms" },
  { key: "statements", label: "정산서", path: "/statements" },
  { key: "results", label: "대조 결과", path: "/results" },
  { key: "qa", label: "질문하기", path: "/qa" },
];

const WIDTH = { md: "max-w-md", "2xl": "max-w-2xl", "3xl": "max-w-3xl", "5xl": "max-w-5xl" } as const;

export const DEMO = process.env.NEXT_PUBLIC_DEMO_MODE === "1";

export function Logo() {
  return (
    <Link href="/" className="flex items-center gap-2 font-bold tracking-tight text-teal-900">
      <span
        aria-hidden
        className="grid h-8 w-8 place-items-center rounded-lg bg-teal-800 text-sm font-black text-white shadow-sm"
      >
        OB
      </span>
      <span className="text-lg">오픈북</span>
    </Link>
  );
}

function StepNav({ step }: { step: Step }) {
  const id = useSearchParams().get("id");
  const at = STEPS.findIndex((s) => s.key === step);
  return (
    <nav aria-label="진행 단계" className="overflow-x-auto [scrollbar-width:none]">
      <ol className="flex min-w-max items-center gap-1 text-sm">
        {STEPS.map((s, i) => {
          const current = s.key === step;
          const done = i < at;
          const href = s.key === "upload" ? "/" : id ? `${s.path}?id=${id}` : null;
          const badge = (
            <span
              className={
                "grid h-5 w-5 place-items-center rounded-full text-[11px] font-bold " +
                (current ? "bg-white text-teal-800" : done ? "bg-teal-700 text-white" : "bg-stone-200 text-stone-500")
              }
            >
              {done ? "✓" : i + 1}
            </span>
          );
          const cls =
            "flex items-center gap-1.5 rounded-full px-3 py-1.5 transition " +
            (current
              ? "bg-teal-800 font-semibold text-white shadow-sm"
              : "text-stone-600 hover:bg-stone-100 hover:text-stone-900");
          return (
            <li key={s.key} className="flex items-center gap-1">
              {i > 0 && <span aria-hidden className="h-px w-3 bg-stone-300" />}
              {href && !current ? (
                <Link className={cls} href={href}>
                  {badge}
                  <span className={current ? "" : "hidden sm:inline"}>{s.label}</span>
                </Link>
              ) : (
                <span className={cls} aria-current={current ? "step" : undefined}>
                  {badge}
                  <span className={current ? "" : "hidden sm:inline"}>{s.label}</span>
                </span>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

export default function Shell({
  step,
  width = "3xl",
  right,
  children,
}: {
  step?: Step;
  width?: keyof typeof WIDTH;
  right?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="flex min-h-screen flex-col text-stone-900">
      {DEMO && (
        <div className="bg-amber-100 px-4 py-2 text-center text-sm text-amber-900">
          <strong className="font-semibold">데모 버전</strong> · 화면의 계약서·정산서는 모두 가상 데이터입니다.
        </div>
      )}
      <header className="sticky top-0 z-10 border-b border-stone-200/80 bg-white/85 backdrop-blur">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-3 px-5 py-3">
          <Logo />
          {step ? (
            <Suspense>
              <StepNav step={step} />
            </Suspense>
          ) : null}
          {right}
        </div>
      </header>
      <main className={`mx-auto w-full ${WIDTH[width]} flex-1 space-y-5 px-5 py-8`}>{children}</main>
      <footer className="border-t border-stone-200 bg-white/60 px-5 py-6 text-center text-xs text-stone-500">
        오픈북은 계약서와 정산서를 대조해 확인할 점을 보여 줄 뿐, 법률·세무 자문이 아닙니다.
      </footer>
    </div>
  );
}
