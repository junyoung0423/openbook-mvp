"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState, type KeyboardEvent } from "react";
import { Card } from "../../components/Card";
import { EmptyState } from "../../components/EmptyState";
import { InfoPanel } from "../../components/InfoPanel";
import { Notice } from "../../components/Notice";
import { ProcessingState } from "../../components/Spinner";
import { SourceQuote } from "../../components/SourceQuote";
import { api, ApiError, errorText, type Clause, type PeriodReconciliation, type ReconciliationReport } from "../../lib/api";
import { periodTab, periodTitle, won } from "../../lib/format";
import { buttonClass } from "../../lib/ui";

// 세부 대조: 작가지급액 아래 두 줄. 정산서에 그 칸이 없으면(null) "정산서에 없음"만 보인다.
function detailRows(r: PeriodReconciliation) {
  return [
    { label: "정산액 (작가 몫)", computed: r.computed_settlement, reported: r.reported_settlement, diff: r.settlement_diff },
    { label: "원천징수 (3.3%)", computed: r.computed_withholding, reported: r.reported_withholding, diff: r.withholding_diff },
  ];
}

const NOT_IN_STATEMENT = <span className="font-normal text-muted">정산서에 없음</span>;

// 계약서 기준 / 정산서 / 차이 세 숫자. 색은 셋 다 잉크색이고, 차이만 굵기를 한 단계 더 준다.
// 넓은 화면은 칸 셋, 좁은 화면은 한 상자 안에 세 줄(라벨 왼쪽, 숫자 오른쪽).
function Figures({ r }: { r: PeriodReconciliation }) {
  const cells = [
    { short: "계약서 기준", long: "작가지급액 · 계약서 기준", value: won(r.computed_payout), diff: false },
    { short: "정산서", long: "작가지급액 · 정산서", value: won(r.reported_payout), diff: false },
    { short: "차이", long: "차이", value: r.diff == null ? "—" : won(r.diff), diff: true },
  ];
  return (
    <dl className="flex flex-col overflow-hidden rounded-[7px] border border-line md:grid md:grid-cols-3 md:gap-2.5 md:overflow-visible md:rounded-none md:border-0">
      {cells.map((c) => (
        <div
          key={c.short}
          className={`flex items-baseline justify-between gap-3 px-3.5 py-3 md:block md:rounded-tile md:px-5 md:py-[18px] ${
            c.diff ? "bg-surface" : "border-b border-line-soft md:border md:border-line"
          }`}
        >
          <dt className={`text-small ${c.diff ? "font-[650] text-ink-2 md:font-normal md:text-muted" : "text-muted"}`}>
            <span className="md:hidden">{c.short}</span>
            <span className="hidden md:inline">{c.long}</span>
          </dt>
          <dd
            className={`num tracking-[-0.02em] md:mt-2 md:text-[28px] ${
              c.diff ? "text-[24px] font-[850]" : "text-[20px] font-bold"
            }`}
          >
            {c.value}
          </dd>
        </div>
      ))}
    </dl>
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
  const [stepsOpen, setStepsOpen] = useState(false);
  const [openClause, setOpenClause] = useState(-1);
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

  const title = periodTitle(r.period_start, r.period_end);
  const range = `${r.period_start} ~ ${r.period_end}`;

  return (
    <Card
      id={`period-${r.statement_id}`}
      role="tabpanel"
      aria-labelledby={`tab-${r.statement_id}`}
      className="flex flex-col gap-5 !p-[18px] md:!px-7 md:!py-[26px]"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-x-3">
        <h3 className="text-[18px] font-[750] md:text-title">{title}</h3>
        {title !== range && <span className="num hidden text-small text-muted md:inline">{range}</span>}
        {r.status === "computed" && <span className="text-fine text-muted md:hidden">작가지급액 기준</span>}
      </div>

      {r.status === "computed" && <Figures r={r} />}

      <p className="text-[14px] leading-[1.7] text-[#2a2e3d] md:text-[15px]">{r.summary}</p>

      {r.status === "computed" && (
        <div className="flex flex-col gap-1.5">
          <h4 className="text-sm font-bold">세부 대조</h4>
          {/* 넓은 화면: 작은 표 */}
          <div className="hidden overflow-x-auto md:block">
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr className="text-right text-fine text-muted">
                  <th scope="col" className="py-2 text-left font-medium">
                    항목
                  </th>
                  <th scope="col" className="py-2 font-medium">
                    계약서 기준
                  </th>
                  <th scope="col" className="py-2 font-medium">
                    정산서
                  </th>
                  <th scope="col" className="py-2 font-medium">
                    차이
                  </th>
                </tr>
              </thead>
              <tbody>
                {detailRows(r).map((row) => (
                  <tr key={row.label} className="border-t border-line-soft">
                    <th scope="row" className="py-[11px] text-left font-medium">
                      {row.label}
                    </th>
                    <td className="num py-[11px] text-right">{won(row.computed)}</td>
                    <td className="num py-[11px] text-right">{row.reported == null ? NOT_IN_STATEMENT : won(row.reported)}</td>
                    <td className="num py-[11px] text-right font-bold">{row.diff == null ? "—" : won(row.diff)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {/* 좁은 화면: 항목별 묶음 (라벨 위, 숫자 셋 아래) */}
          <div className="flex flex-col gap-2 md:hidden">
            {detailRows(r).map((row) => (
              <div key={row.label} className="flex flex-col gap-1 rounded-field border border-line-soft px-3 py-2.5 text-[13px]">
                <span className="font-[650]">{row.label}</span>
                <span className="num flex justify-between text-ink-2">
                  <span>계약서 기준</span>
                  <span>{won(row.computed)}</span>
                </span>
                <span className="num flex justify-between text-ink-2">
                  <span>정산서</span>
                  <span>{row.reported == null ? NOT_IN_STATEMENT : won(row.reported)}</span>
                </span>
                <span className="num flex justify-between font-bold">
                  <span>차이</span>
                  <span>{row.diff == null ? "—" : won(row.diff)}</span>
                </span>
              </div>
            ))}
          </div>
          {r.mg_balance_after != null && <p className="num text-fine text-muted md:text-small">이 기간 뒤 남은 MG · {won(r.mg_balance_after)}</p>}
        </div>
      )}

      {r.breakdown.length > 0 && (
        <div className="border-t border-line-soft pt-4">
          <button
            type="button"
            aria-expanded={stepsOpen}
            aria-controls={`steps-${r.statement_id}`}
            onClick={() => setStepsOpen((v) => !v)}
            className="min-h-11 rounded-btn border border-line bg-card px-[18px] text-sm font-[650] text-ink hover:bg-surface"
          >
            {stepsOpen ? "계산 내역 접기" : `계산 내역 ${r.breakdown.length}단계 보기`}
          </button>
          {stepsOpen && (
            <ol id={`steps-${r.statement_id}`} className="mt-3 overflow-hidden rounded-tile border border-line">
              {r.breakdown.map((s, i) => {
                const clause = s.source_clause_id ? clauseOf(s.source_clause_id) : undefined;
                const label = s.source_clause_id ? clauseLabel(s.source_clause_id) : "";
                return (
                  <li
                    key={i}
                    className="flex flex-col gap-1 border-t border-line-soft px-4 py-3 text-sm first:border-t-0 md:grid md:grid-cols-[180px_130px_minmax(0,1fr)] md:items-start md:gap-4"
                  >
                    <span className="font-semibold">{s.label}</span>
                    <span className="num font-bold md:text-right">{won(s.value)}</span>
                    <span className="min-w-0 leading-[1.55] text-muted">
                      {s.formula && <span className="num block break-words font-mono text-[12.5px]">{s.formula}</span>}
                      {s.source_clause_id &&
                        (clause ? (
                          <button
                            type="button"
                            aria-expanded={openClause === i}
                            onClick={() => setOpenClause(openClause === i ? -1 : i)}
                            className="mt-1.5 inline-flex min-h-8 items-center rounded-tag bg-accent-soft px-2.5 py-1 text-fine font-[650] text-accent"
                          >
                            근거 · {label}
                          </button>
                        ) : (
                          <span className="mt-1.5 block text-fine">근거 · {label}</span>
                        ))}
                      {clause && openClause === i && (
                        <SourceQuote label={label} className="mt-2">
                          {clause.text}
                        </SourceQuote>
                      )}
                    </span>
                  </li>
                );
              })}
            </ol>
          )}
        </div>
      )}

      {r.questions.length > 0 && (
        <div className="flex flex-col gap-2.5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h4 className="text-[15px] font-bold md:text-base">
              플랫폼에 확인할 질문 <span className="num font-medium text-muted">{r.questions.length}개</span>
            </h4>
            <button type="button" onClick={copyQuestions} className={`${buttonClass("dark")} !min-h-11 !px-4 !text-[13px] !font-[650]`}>
              {copy === "done" ? "복사했습니다" : copy === "fail" ? "복사하지 못했습니다" : "질문 복사"}
            </button>
          </div>
          <span role="status" className="sr-only">
            {copy === "done" && "질문을 복사했습니다"}
            {copy === "fail" && "복사하지 못했습니다. 질문을 직접 선택해 복사해 주세요."}
          </span>
          <ol className="flex list-decimal flex-col gap-2 pl-5 text-[14px] leading-relaxed md:pl-[22px] md:text-[15px]">
            {r.questions.map((q, i) => (
              <li key={i}>{q}</li>
            ))}
          </ol>
        </div>
      )}
    </Card>
  );
}

// 월별 탭: 한 번에 한 달만 보여 준다. 차이는 모든 탭에 같은 색·같은 굵기로 적는다.
function MonthTabs({ items, selected, onSelect }: { items: PeriodReconciliation[]; selected: string; onSelect: (id: string) => void }) {
  const withYear = new Set(items.map((r) => r.period_start.slice(0, 4))).size > 1;
  const refs = useRef<(HTMLButtonElement | null)[]>([]);

  function onKeyDown(e: KeyboardEvent<HTMLButtonElement>, index: number) {
    const next = e.key === "ArrowRight" ? index + 1 : e.key === "ArrowLeft" ? index - 1 : e.key === "Home" ? 0 : e.key === "End" ? items.length - 1 : -1;
    if (next < 0 || next >= items.length) return;
    e.preventDefault();
    onSelect(items[next].statement_id);
    refs.current[next]?.focus();
  }

  return (
    <div role="tablist" aria-label="정산 기간" className="grid grid-cols-4 gap-1.5 md:gap-2">
      {items.map((r, i) => {
        const on = r.statement_id === selected;
        return (
          <button
            key={r.statement_id}
            ref={(el) => {
              refs.current[i] = el;
            }}
            id={`tab-${r.statement_id}`}
            type="button"
            role="tab"
            aria-selected={on}
            aria-controls={`period-${r.statement_id}`}
            tabIndex={on ? 0 : -1}
            onClick={() => onSelect(r.statement_id)}
            onKeyDown={(e) => onKeyDown(e, i)}
            className={`min-h-[52px] rounded-[7px] border-[1.5px] bg-card px-1 py-1.5 text-center text-ink md:min-h-[62px] md:rounded-tile md:px-4 md:py-2.5 md:text-left ${
              on ? "border-accent shadow-[0_2px_8px_rgb(70_85_232/0.12)]" : "border-transparent"
            }`}
          >
            <span className="block text-sm font-bold md:text-[15px]">{periodTab(r.period_start, r.period_end, withYear)}</span>
            {r.status === "computed" && r.diff != null && (
              <span className="num mt-0.5 block text-[11px] text-muted md:mt-[3px] md:text-small">
                <span className="hidden md:inline">차이 </span>
                {won(r.diff)}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}

function ResultsInner() {
  const id = useSearchParams().get("id") ?? "";
  const [report, setReport] = useState<ReconciliationReport | null>(null);
  const [error, setError] = useState<{ text: string; code?: string } | null>(null);
  const [clauses, setClauses] = useState<Clause[]>([]);
  const [clauseError, setClauseError] = useState("");
  const [clausesContractId, setClausesContractId] = useState("");
  // 고른 달. 아직 고르지 않았으면 가장 최근 달
  const [picked, setPicked] = useState("");

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

  if (!id)
    return (
      <EmptyState
        message="계약서를 먼저 선택해 주세요."
        action={
          <Link className={buttonClass("primary")} href="/">
            계약서 올리러 가기
          </Link>
        }
      />
    );
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

  const items = report.items;
  const current = items.find((r) => r.statement_id === picked) ?? items[items.length - 1];

  return (
    <>
      <Card className="flex flex-col gap-2">
        <h2 className="text-title font-[750]">정산 대조 결과</h2>
        <p className="text-[15px] leading-relaxed text-[#3a3f52]">{report.diff_meaning}</p>
        <details className="text-sm text-muted">
          <summary className="flex min-h-11 cursor-pointer items-center font-semibold text-accent">계산 기준 보기</summary>
          <Notice className="mt-1 !text-sm">
            원천징수는 사업소득 3.3%(소득세 3% + 지방소득세 0.3%, 각각 10원 미만 버림) 기준으로 계산합니다. 기타소득(8.8%) 등 다른 방식으로
            떼는 계약이면 원천징수와 작가지급액에 차이가 날 수 있습니다.
          </Notice>
        </details>
      </Card>

      {report.unsupported_reason && (
        <InfoPanel role="alert" title={report.unsupported_reason}>
          <p>
            틀린 숫자를 보여 드리지 않으려고 이 계약은 금액을 계산하지 않았습니다. 아래 질문으로 플랫폼에 확인하거나, 빠진 정산서·조건을 채운 뒤
            다시 확인해 주세요.
          </p>
        </InfoPanel>
      )}

      {items.length === 0 && (
        <EmptyState
          message="아직 입력한 정산서가 없습니다"
          action={
            <Link className={buttonClass("primary")} href={`/statements?id=${id}`}>
              정산서 입력하기
            </Link>
          }
        />
      )}

      {items.length > 1 && <MonthTabs items={items} selected={current.statement_id} onSelect={setPicked} />}
      {current && <PeriodCard key={current.statement_id} r={current} clauseLabel={clauseLabel} clauseOf={clauseOf} />}

      <p className="px-1 text-small leading-relaxed text-muted">
        {report.notice} <span className="num">계산 규칙 {report.rules_version} · 원천징수 사업소득 3.3% 기준</span>
      </p>

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
    <Suspense>
      <ResultsInner />
    </Suspense>
  );
}
