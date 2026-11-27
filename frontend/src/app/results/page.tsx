"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import { AppShell, useContract } from "../../components/AppShell";
import { Button } from "../../components/Button";
import { Card, CardHeader } from "../../components/Card";
import { EmptyState } from "../../components/EmptyState";
import { InfoPanel } from "../../components/InfoPanel";
import { Notice } from "../../components/Notice";
import { ProcessingState } from "../../components/Spinner";
import { SourceQuote } from "../../components/SourceQuote";
import { api, ApiError, errorText, type Clause, type PeriodReconciliation, type ReconciliationReport } from "../../lib/api";
import { isZeroAmount, periodChip, periodTitle, won } from "../../lib/format";
import { buttonClass } from "../../lib/ui";

// 세부 대조: 작가지급액 아래 두 줄. 정산서에 그 칸이 없으면(null) "정산서에 없음"만 보인다.
function detailRows(r: PeriodReconciliation) {
  return [
    { label: "정산액 (작가 몫)", computed: r.computed_settlement, reported: r.reported_settlement, diff: r.settlement_diff },
    { label: "원천징수 (3.3%)", computed: r.computed_withholding, reported: r.reported_withholding, diff: r.withholding_diff },
  ];
}

const NOT_IN_STATEMENT = <span className="text-small font-normal text-muted">정산서에 없음</span>;

function Figure({ label, value, strong = false }: { label: string; value: string; strong?: boolean }) {
  return (
    <div className="rounded-control border border-line bg-paper px-4 py-3">
      <dt className="text-small text-muted">{label}</dt>
      <dd className={`num mt-1 text-right text-page leading-tight ${strong ? "font-extrabold" : "font-bold"}`}>{value}</dd>
    </div>
  );
}

function PeriodCard({
  r,
  clauseLabel,
  clauseOf,
}: {
  r: PeriodReconciliation;
  clauseLabel: (id: string) => string;
  clauseOf: (id: string) => Clause | undefined;
}) {
  const [openSteps, setOpenSteps] = useState<Record<number, boolean>>({});
  const [copy, setCopy] = useState<"" | "done" | "fail">("");
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  useEffect(() => () => clearTimeout(timer.current), []);

  async function copyQuestions() {
    try {
      await navigator.clipboard.writeText(r.questions.join("\n"));
      setCopy("done");
    } catch {
      setCopy("fail");
    }
    clearTimeout(timer.current);
    timer.current = setTimeout(() => setCopy(""), 3000);
  }

  return (
    <Card id={`period-${r.statement_id}`} className="scroll-mt-20 space-y-6">
      <CardHeader as="h2" title={periodTitle(r.period_start, r.period_end)} />

      {r.status === "computed" && (
        <div>
          <p className="mb-2 text-small text-muted">작가지급액 (원천징수 뒤) 기준</p>
          <dl className="grid gap-3 sm:grid-cols-3">
            <Figure label="계약서 기준" value={won(r.computed_payout)} />
            <Figure label="정산서" value={won(r.reported_payout)} />
            <Figure label="차이" value={r.diff == null ? "—" : won(r.diff)} strong />
          </dl>
        </div>
      )}

      <p className="text-card">{r.summary}</p>

      {r.status === "computed" && (
        <div>
          <h3 className="mb-2 font-semibold">세부 대조</h3>
          {/* 넓은 화면: 작은 표 */}
          <table className="hidden w-full text-left sm:table">
            <thead className="text-small text-muted">
              <tr>
                <th className="py-2 pr-3 font-medium">항목</th>
                <th className="py-2 pr-3 text-right font-medium">계약서 기준</th>
                <th className="py-2 pr-3 text-right font-medium">정산서</th>
                <th className="py-2 text-right font-medium">차이</th>
              </tr>
            </thead>
            <tbody>
              {detailRows(r).map((row) => (
                <tr key={row.label} className="border-t border-line">
                  <td className="py-3 pr-3">{row.label}</td>
                  <td className="num py-3 pr-3 text-right whitespace-nowrap">{won(row.computed)}</td>
                  <td className="num py-3 pr-3 text-right whitespace-nowrap">{row.reported == null ? NOT_IN_STATEMENT : won(row.reported)}</td>
                  <td className="num py-3 text-right whitespace-nowrap">{row.diff == null ? "—" : won(row.diff)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {/* 좁은 화면: 항목별 묶음 (라벨 위, 숫자 셋 아래) */}
          <div className="space-y-3 sm:hidden">
            {detailRows(r).map((row) => (
              <dl key={row.label} className="rounded-control border border-line p-3">
                <dt className="font-medium">{row.label}</dt>
                {(
                  [
                    ["계약서 기준", won(row.computed)],
                    ["정산서", row.reported == null ? NOT_IN_STATEMENT : won(row.reported)],
                    ["차이", row.diff == null ? "—" : won(row.diff)],
                  ] as const
                ).map(([k, v]) => (
                  <div key={k} className="mt-1 flex items-baseline justify-between gap-3">
                    <dt className="text-small text-muted">{k}</dt>
                    <dd className="num text-right">{v}</dd>
                  </div>
                ))}
              </dl>
            ))}
          </div>
          {r.mg_balance_after != null && (
            <p className="mt-3 text-small text-muted">
              이 기간 뒤 남은 MG: <span className="num">{won(r.mg_balance_after)}</span>
            </p>
          )}
        </div>
      )}

      {r.breakdown.length > 0 && (
        <details className="group">
          <summary className="flex min-h-11 cursor-pointer items-center font-medium text-brand underline underline-offset-2">
            계산 내역 {r.breakdown.length}단계 보기
          </summary>
          <ol className="mt-2 divide-y divide-line border-t border-line">
            {r.breakdown.map((s, i) => {
              const clause = s.source_clause_id ? clauseOf(s.source_clause_id) : undefined;
              const label = s.source_clause_id ? clauseLabel(s.source_clause_id) : "";
              return (
                <li key={i} className="grid gap-x-4 gap-y-1 py-3 sm:grid-cols-[minmax(0,2fr)_auto_minmax(0,3fr)]">
                  <span>{s.label}</span>
                  <span className="num font-semibold whitespace-nowrap sm:text-right">{won(s.value)}</span>
                  <div className="min-w-0 text-small text-muted">
                    {s.formula && <p className="font-mono break-words">{s.formula}</p>}
                    {s.source_clause_id &&
                      (clause ? (
                        <button
                          type="button"
                          aria-expanded={!!openSteps[i]}
                          onClick={() => setOpenSteps((o) => ({ ...o, [i]: !o[i] }))}
                          className="inline-flex min-h-11 items-center font-medium text-brand underline underline-offset-2"
                        >
                          근거 · {label}
                        </button>
                      ) : (
                        <p>근거 · {label}</p>
                      ))}
                  </div>
                  {clause && openSteps[i] && (
                    <SourceQuote label={label} className="sm:col-span-3">
                      {clause.text}
                    </SourceQuote>
                  )}
                </li>
              );
            })}
          </ol>
        </details>
      )}

      {r.questions.length > 0 && (
        <div>
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <h3 className="font-semibold">플랫폼에 확인할 질문</h3>
            <span className="flex items-center gap-3">
              <span role="status" className="text-small text-muted">
                {copy === "done" && "복사했습니다"}
                {copy === "fail" && "복사하지 못했습니다. 질문을 직접 선택해 복사해 주세요."}
              </span>
              <Button variant="secondary" onClick={copyQuestions}>
                질문 복사
              </Button>
            </span>
          </div>
          <ol className="list-decimal space-y-1 pl-6">
            {r.questions.map((q, i) => (
              <li key={i}>{q}</li>
            ))}
          </ol>
        </div>
      )}
    </Card>
  );
}

// 기간 바로가기: 누르면 그 기간 카드로 스크롤. 차이는 모든 칩에 같은 색으로, 0이 아니면 굵기만 한 단계 더 준다.
function PeriodChips({ items }: { items: PeriodReconciliation[] }) {
  const withYear = new Set(items.map((r) => r.period_start.slice(0, 4))).size > 1;
  return (
    <nav aria-label="기간 바로가기" className="sticky top-0 z-10 -mx-4 bg-paper px-4 py-2 sm:-mx-6 sm:px-6">
      <ul className="flex flex-wrap gap-2">
        {items.map((r) => (
          <li key={r.statement_id}>
            <a
              href={`#period-${r.statement_id}`}
              className="flex min-h-11 flex-col justify-center rounded-control border border-line bg-surface px-3 hover:bg-brand-soft"
            >
              <span className="text-small font-medium">{periodChip(r.period_start, r.period_end, withYear)}</span>
              {r.status === "computed" && r.diff != null && (
                <span className={`num text-fine text-muted ${isZeroAmount(r.diff) ? "" : "font-semibold"}`}>차이 {won(r.diff)}</span>
              )}
            </a>
          </li>
        ))}
      </ul>
    </nav>
  );
}

function ResultsInner() {
  const id = useSearchParams().get("id") ?? "";
  const { contract } = useContract();
  const [report, setReport] = useState<ReconciliationReport | null>(null);
  const [error, setError] = useState<{ text: string; code?: string } | null>(null);
  const [clauses, setClauses] = useState<Clause[]>([]);
  const [clauseError, setClauseError] = useState("");
  const [clausesContractId, setClausesContractId] = useState("");

  useEffect(() => {
    if (!id) return;

    let cancelled = false;

    api<Clause[]>(`/contracts/${id}/clauses`).then(
      (res) => {
        if (cancelled) return;
        setClauses(res);
        setClauseError("");
        setClausesContractId(id);
      },
      () => {
        if (cancelled) return;
        setClauses([]);
        setClauseError("조항 번호와 제목을 불러오지 못했습니다.");
        setClausesContractId(id);
      },
    );

    return () => {
      cancelled = true;
    };
  }, [id]);

  const clauseOf = (clauseId: string) => (clausesContractId === id ? clauses.find((item) => item.id === clauseId) : undefined);

  function clauseLabel(clauseId: string) {
    if (clausesContractId !== id) return "조항 정보 불러오는 중…";

    const clause = clauseOf(clauseId);
    if (!clause) return clauseError || "조항 정보를 확인할 수 없습니다.";

    const no = clause.no?.trim() || "번호 없는 조항";
    const title = clause.title?.trim();

    return title ? `${no} (${title})` : no;
  }

  useEffect(() => {
    if (!id) return;
    api<ReconciliationReport>(`/contracts/${id}/reconciliations`).then(setReport, (e) =>
      setError({ text: errorText(e), code: e instanceof ApiError ? e.code : undefined }),
    );
  }, [id]);

  if (!id) return <EmptyState message="계약서를 먼저 선택해 주세요." action={<Link className={buttonClass("primary")} href="/">내 계약서 보기</Link>} />;
  if (error)
    return (
      <InfoPanel role="alert" title={error.text}>
        {error.code === "TERMS_NOT_CONFIRMED" && (
          <Link className={buttonClass("secondary")} href={`/terms?id=${id}`}>
            조건 확인하러 가기
          </Link>
        )}
      </InfoPanel>
    );
  if (!report) return <ProcessingState>대조 결과를 계산하는 중입니다.</ProcessingState>;

  return (
    <>
      <Card>
        <CardHeader as="h1" title="정산 대조 결과" description={contract?.title} />
        <p className="text-card">{report.diff_meaning}</p>
        <details className="mt-2">
          <summary className="flex min-h-11 cursor-pointer items-center text-small font-medium text-brand underline underline-offset-2">
            계산 기준 보기
          </summary>
          <Notice>
            원천징수는 사업소득 3.3%(소득세 3% + 지방소득세 0.3%, 각각 10원 미만 버림) 기준으로 계산합니다. 기타소득(8.8%) 등 다른 방식으로
            떼는 계약이면 원천징수와 작가지급액에 차이가 날 수 있습니다.
          </Notice>
        </details>
      </Card>

      {report.items.length > 1 && <PeriodChips items={report.items} />}

      {report.unsupported_reason && (
        <InfoPanel role="alert" title={report.unsupported_reason}>
          <p>
            틀린 숫자를 보여 드리지 않으려고 이 계약은 금액을 계산하지 않았습니다. 아래 질문으로 플랫폼에 확인하거나, 빠진 정산서·조건을 채운 뒤
            다시 확인해 주세요.
          </p>
        </InfoPanel>
      )}

      {report.items.length === 0 && (
        <EmptyState
          message="아직 입력한 정산서가 없습니다"
          action={
            <Link className={buttonClass("primary")} href={`/statements?id=${id}`}>
              정산서 입력하기
            </Link>
          }
        />
      )}

      {report.items.map((r) => (
        <PeriodCard key={r.statement_id} r={r} clauseLabel={clauseLabel} clauseOf={clauseOf} />
      ))}

      <Notice>
        <p>{report.notice}</p>
        <p className="mt-1">계산 규칙 버전 {report.rules_version}</p>
      </Notice>

      <div className="flex flex-wrap gap-2">
        <Link className={buttonClass("secondary")} href={`/statements?id=${id}`}>
          정산서 더 입력하기
        </Link>
        <Link className={buttonClass("secondary")} href={`/qa?id=${id}`}>
          계약서에 질문하기
        </Link>
      </div>
    </>
  );
}

export default function ResultsPage() {
  return (
    <AppShell step="results" width="wide">
      <Suspense>
        <ResultsInner />
      </Suspense>
    </AppShell>
  );
}
