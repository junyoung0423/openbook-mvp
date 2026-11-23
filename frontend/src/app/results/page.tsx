"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { api, ApiError, errorText, secondary, won, type ReconciliationReport } from "../../lib/api";

function ResultsInner() {
  const id = useSearchParams().get("id") ?? "";
  const [report, setReport] = useState<ReconciliationReport | null>(null);
  const [error, setError] = useState<{ text: string; code?: string } | null>(null);

  useEffect(() => {
    if (!id) return;
    api<ReconciliationReport>(`/contracts/${id}/reconciliations`).then(setReport, (e) =>
      setError({ text: errorText(e), code: e instanceof ApiError ? e.code : undefined }),
    );
  }, [id]);

  if (!id) return <p className="rounded-2xl bg-white p-6">계약서를 먼저 선택해 주세요.</p>;
  if (error)
    return (
      <section className="space-y-3 rounded-2xl bg-white p-6">
        <p role="alert">{error.text}</p>
        {error.code === "TERMS_NOT_CONFIRMED" && (
          <Link className={secondary + " inline-block"} href={`/terms?id=${id}`}>
            조건 확인하러 가기
          </Link>
        )}
      </section>
    );
  if (!report) return <p role="status" className="rounded-2xl bg-white p-6">계산 중…</p>;

  return (
    <>
      <section className="rounded-2xl bg-white p-6">
        <h1 className="text-3xl font-bold">정산 대조 결과</h1>
        <p className="mt-3 text-stone-600">{report.diff_meaning}</p>
        {report.rules_version.startsWith("provisional") && (
          <p className="mt-2 text-sm text-stone-600">계산 규칙은 검토 중인 임시 안입니다 ({report.rules_version}).</p>
        )}
      </section>

      {report.items.length === 0 && (
        <section className="space-y-3 rounded-2xl bg-white p-6">
          <p>아직 입력한 정산서가 없습니다.</p>
          <Link className={secondary + " inline-block"} href={`/statements?id=${id}`}>
            정산서 입력하러 가기
          </Link>
        </section>
      )}

      {report.items.map((r) => (
        <article key={r.statement_id} className="space-y-4 rounded-2xl bg-white p-6">
          <h2 className="text-xl font-bold">
            {r.period_start} ~ {r.period_end}
          </h2>
          <p className="text-lg">{r.summary}</p>

          {r.status === "computed" && (
            <div className="grid gap-3 sm:grid-cols-3">
              {[
                ["계약서 기준 금액", r.computed_payout],
                ["정산서 금액", r.reported_payout],
                ["차이", r.diff],
              ].map(([label, value]) => (
                <div key={label} className="rounded-xl bg-stone-100 p-4">
                  <p className="text-sm">{label}</p>
                  <p className="mt-2 text-2xl font-bold">{won(value)}</p>
                </div>
              ))}
            </div>
          )}

          {r.breakdown.length > 0 && (
            <details open>
              <summary className="cursor-pointer font-medium">계산 내역</summary>
              <table className="mt-3 w-full text-left text-sm">
                <tbody>
                  {r.breakdown.map((s, i) => (
                    <tr key={i} className="border-t border-stone-200 align-top">
                      <td className="py-2 pr-3">{s.label}</td>
                      <td className="py-2 pr-3 font-medium whitespace-nowrap">{won(s.value)}</td>
                      <td className="py-2 text-stone-600">
                        {s.formula}
                        {s.source_clause_id && <span className="block">근거 조항 · {s.source_clause_id}</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </details>
          )}

          {r.questions.length > 0 && (
            <div>
              <h3 className="font-semibold">플랫폼에 확인할 질문</h3>
              <ul className="mt-2 list-disc space-y-1 pl-5">
                {r.questions.map((q) => (
                  <li key={q}>{q}</li>
                ))}
              </ul>
            </div>
          )}
        </article>
      ))}

      <section className="rounded-2xl bg-white p-6 text-stone-600">{report.notice}</section>
      <Link className={secondary + " inline-block"} href={`/statements?id=${id}`}>
        정산서 입력으로 돌아가기
      </Link>
    </>
  );
}

export default function ResultsPage() {
  return (
    <main className="min-h-screen bg-stone-100 px-4 py-10 text-stone-900">
      <div className="mx-auto max-w-5xl space-y-6">
        <Link href="/" className="font-bold text-teal-900">
          오픈북
        </Link>
        <Suspense>
          <ResultsInner />
        </Suspense>
      </div>
    </main>
  );
}
