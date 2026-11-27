"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { AppShell } from "../../components/AppShell";
import {
    api,
    ApiError,
    errorText,
    secondary,
    won,
    type Clause,
    type PeriodReconciliation,
    type ReconciliationReport,
} from "../../lib/api";

// 정산서 칸별 대조. 정산서에 그 칸이 없으면(null) 계약서 기준 값만 보인다.
function rows(r: PeriodReconciliation) {
    return [
        { label: "작가지급액 (원천징수 뒤)", computed: r.computed_payout, reported: r.reported_payout, diff: r.diff, main: true },
        { label: "정산액 (작가 몫)", computed: r.computed_settlement, reported: r.reported_settlement, diff: r.settlement_diff, main: false },
        { label: "원천징수 (3.3%)", computed: r.computed_withholding, reported: r.reported_withholding, diff: r.withholding_diff, main: false },
    ];
}

// 원천징수는 정산서가 더 많아도 작가에게 불리하므로, 차이가 있으면 방향과 관계없이 같은 색으로 표시한다.
const diffColor = (d: string | null) => (d == null || Number(d) === 0 ? "" : "text-red-700");

function ResultsInner() {
    const id = useSearchParams().get("id") ?? "";
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

    function clauseLabel(clauseId: string | null | undefined) {
        if (!clauseId) return "연결된 조항 없음";
        if (clausesContractId !== id) return "조항 정보 불러오는 중…";

        const clause = clauses.find((item) => item.id === clauseId);
        if (!clause) {
            return clauseError || "조항 정보를 확인할 수 없습니다.";
        }

        const no = clause.no?.trim() || "번호 없는 조항";
        const title = clause.title?.trim();

        return title ? `${no} ${title}` : no;
    }
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
                <p className="mt-2 text-sm text-stone-600">
                    원천징수는 사업소득 3.3%(소득세 3% + 지방소득세 0.3%, 각각 10원 미만 버림) 기준으로 계산합니다.
                    기타소득(8.8%) 등 다른 방식으로 떼는 계약이면 원천징수와 작가지급액에 차이가 날 수 있습니다.
                </p>
                {(report.rules_version.startsWith("provisional") || report.rules_version.startsWith("draft")) && (
                    <p className="mt-2 text-sm text-stone-600">계산 규칙은 검토 중인 임시 안입니다 ({report.rules_version}).</p>
                )}
            </section>

            {report.unsupported_reason && (
                <section role="alert" className="space-y-2 rounded-2xl border border-amber-300 bg-amber-50 p-6">
                    <p className="text-lg font-semibold">{report.unsupported_reason}</p>
                    <p className="text-stone-700">
                        틀린 숫자를 보여 드리지 않으려고 이 계약은 금액을 계산하지 않았습니다. 아래 질문으로 플랫폼에 확인하거나,
                        빠진 정산서·조건을 채운 뒤 다시 확인해 주세요.
                    </p>
                </section>
            )}

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
                        <div className="overflow-x-auto">
                            <table className="w-full min-w-[32rem] text-left">
                                <thead className="text-sm text-stone-600">
                                    <tr>
                                        <th className="py-2 pr-3 font-medium">항목</th>
                                        <th className="py-2 pr-3 text-right font-medium">계약서 기준</th>
                                        <th className="py-2 pr-3 text-right font-medium">정산서</th>
                                        <th className="py-2 text-right font-medium">차이</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {rows(r).map((row) => (
                                        <tr key={row.label} className={"border-t border-stone-200 " + (row.main ? "text-lg font-bold" : "")}>
                                            <td className="py-2 pr-3">{row.label}</td>
                                            <td className="py-2 pr-3 text-right whitespace-nowrap">{won(row.computed)}</td>
                                            <td className="py-2 pr-3 text-right whitespace-nowrap">
                                                {row.reported == null ? <span className="text-sm font-normal text-stone-500">정산서에 없음</span> : won(row.reported)}
                                            </td>
                                            <td className={"py-2 text-right whitespace-nowrap " + diffColor(row.diff)}>
                                                {row.diff == null ? "—" : won(row.diff)}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                            {r.mg_balance_after != null && (
                                <p className="mt-2 text-sm text-stone-600">이 기간 뒤 남은 MG: {won(r.mg_balance_after)}</p>
                            )}
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
                                                {s.source_clause_id && <span className="block">근거 조항 · {clauseLabel(s.source_clause_id)}</span>}
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
            <div className="flex flex-wrap gap-2">
                <Link className={secondary} href={`/statements?id=${id}`}>
                    정산서 입력으로 돌아가기
                </Link>
                <Link className={secondary} href={`/qa?id=${id}`}>
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
