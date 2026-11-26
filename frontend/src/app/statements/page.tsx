"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState, type FormEvent } from "react";
import {
    api,
    errorText,
    field,
    MONEY,
    primary,
    secondary,
    SIGNED_MONEY,
    won,
    type StatementBody,
    type StatementDraft,
    type StatementOut,
} from "../../lib/api";

// 화면에서는 빈칸을 ""로 다루고, 보낼 때 선택 칸의 ""를 null로 바꾼다.
type Form = {
    period_start: string;
    period_end: string;
    gross: string;
    net_revenue: string;
    deductions: { name: string; amount: string }[];
    reported_settlement: string;
    reported_withholding: string;
    reported_payout: string;
};

const EMPTY: Form = {
    period_start: "",
    period_end: "",
    gross: "",
    net_revenue: "",
    deductions: [],
    reported_settlement: "",
    reported_withholding: "",
    reported_payout: "",
};

// 정산서 칸 순서 그대로 (지급내역형)
const AMOUNTS: { key: "gross" | "net_revenue" | "reported_settlement" | "reported_withholding"; label: string; hint: string }[] = [
    { key: "gross", label: "매출액 (원)", hint: "필수. 환불이 많은 달은 음수(-)도 됩니다." },
    { key: "net_revenue", label: "회사입금액 (원)", hint: "순매출 기준 계약이면 필요합니다." },
    { key: "reported_settlement", label: "정산액 (원)", hint: "작가 몫. 적혀 있으면 계약서 기준과 대조합니다." },
    { key: "reported_withholding", label: "원천징수 (원)", hint: "적혀 있으면 3.3% 계산과 대조합니다." },
];

const toBody = (f: Form): StatementBody => ({
    ...f,
    net_revenue: f.net_revenue || null,
    reported_settlement: f.reported_settlement || null,
    reported_withholding: f.reported_withholding || null,
});

function StatementsInner() {
    const id = useSearchParams().get("id") ?? "";
    const [form, setForm] = useState<Form>(EMPTY);
    const [paste, setPaste] = useState("");
    const [saved, setSaved] = useState<StatementOut[]>([]);
    const [message, setMessage] = useState("");
    const [notes, setNotes] = useState<string[]>([]);
    const [pasteResult, setPasteResult] = useState<StatementDraft | null>(null);
    const refresh = useCallback(async () => {
        try {
            setSaved(await api<StatementOut[]>(`/contracts/${id}/statements`));
        } catch (e) {
            setMessage(errorText(e));
        }
    }, [id]);

    useEffect(() => {
        // eslint-disable-next-line react-hooks/set-state-in-effect
        if (id) void refresh();
    }, [id, refresh]);

    async function readPaste() {
        setMessage("");
        setPasteResult(null);
        setNotes([]);
        try {
            const d = await api<StatementDraft>(`/contracts/${id}/statements/paste`, {
                method: "POST",
                body: JSON.stringify({ text: paste }),
            });
            setForm({
                period_start: d.period_start ?? "",
                period_end: d.period_end ?? "",
                gross: d.gross ?? "",
                net_revenue: d.net_revenue ?? "",
                deductions: d.deductions ?? [],
                reported_settlement: d.reported_settlement ?? "",
                reported_withholding: d.reported_withholding ?? "",
                reported_payout: d.reported_payout ?? "",
            });
            setNotes(d.warnings ?? []);
            setPasteResult(d);
            setMessage("붙여넣은 표에서 읽은 값을 채웠습니다. 정산서와 비교해 확인해 주세요.");
        } catch (e) {
            setMessage(errorText(e));
        }
    }

    async function submit(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        if (!form.period_start || !form.period_end) return setMessage("정산 기간을 입력해 주세요.");
        if (form.period_end < form.period_start) return setMessage("정산 기간의 끝이 시작보다 앞입니다.");
        if (!SIGNED_MONEY.test(form.gross) || !MONEY.test(form.reported_payout))
            return setMessage("매출액과 작가지급액을 쉼표 없이 숫자로 입력해 주세요.");
        if (
            (form.net_revenue && !SIGNED_MONEY.test(form.net_revenue)) ||
            (form.reported_settlement && !SIGNED_MONEY.test(form.reported_settlement)) ||
            (form.reported_withholding && !MONEY.test(form.reported_withholding))
        )
            return setMessage("회사입금액·정산액·원천징수는 비워 두거나 쉼표 없이 숫자로 입력해 주세요.");
        if (form.deductions.some((d) => !d.name.trim() || !MONEY.test(d.amount)))
            return setMessage("공제 항목의 이름과 금액을 확인해 주세요.");
        try {
            await api(`/contracts/${id}/statements`, { method: "POST", body: JSON.stringify(toBody(form)) });
            setForm(EMPTY);
            setPaste("");
            setNotes([]);
            setPasteResult(null);
            setMessage("저장했습니다.");
            await refresh();
        } catch (e) {
            setMessage(errorText(e));
        }
    }

    async function remove(sid: string) {
        if (!window.confirm("이 정산서를 삭제할까요?")) return;
        try {
            await api(`/contracts/${id}/statements/${sid}`, { method: "DELETE" });
            await refresh();
        } catch (e) {
            setMessage(errorText(e));
        }
    }
    function missingMessage(key: keyof Form) {
        if (!pasteResult) return "";

        const missing = (pasteResult as StatementDraft & {
            missing?: string[];
        }).missing ?? [];

        const missingKey =
            key === "period_start" || key === "period_end" ? "period" : key;

        if (!missing.includes(missingKey) || form[key] !== "") return "";

        return "붙여넣은 표에서 찾지 못했습니다. 정산서를 확인해 직접 입력해 주세요.";
    }
    const setDed = (i: number, patch: Partial<{ name: string; amount: string }>) =>
        setForm((f) => ({ ...f, deductions: f.deductions.map((d, j) => (i === j ? { ...d, ...patch } : d)) }));

    if (!id) return <p className="rounded-2xl bg-white p-6">계약서를 먼저 선택해 주세요.</p>;

    return (
        <>
            <section className="space-y-3 rounded-2xl bg-white p-6">
                <h1 className="text-2xl font-bold">정산서 입력</h1>
                <label className="block">
                    정산서 표 붙여넣기 (선택)
                    <textarea className={field} rows={5} value={paste} onChange={(e) => setPaste(e.target.value)} />
                </label>
                <button type="button" className={secondary} disabled={!paste.trim()} onClick={readPaste}>
                    표에서 값 읽기
                </button>
                {pasteResult && (
                    <div className="space-y-4 border-t border-stone-200 pt-4">
                        <p className="text-sm text-stone-600">
                            표를 읽은 시점의 결과입니다. 아래 입력 칸에서 원본과 비교해 확인해 주세요.
                        </p>

                        {[
                            {
                                title: "입력 칸에 반영한 줄",
                                rows: (pasteResult.rows ?? []).filter((row) => row.field != null),
                            },
                            {
                                title: "입력 칸에 반영하지 않은 줄",
                                rows: (pasteResult.rows ?? []).filter((row) => row.field == null),
                            },
                        ].map((group) => (
                            <section key={group.title} className="space-y-2">
                                <h2 className="font-semibold">{group.title}</h2>

                                {group.rows.length === 0 ? (
                                    <p className="text-sm text-stone-600">없습니다.</p>
                                ) : (
                                    <div className="overflow-x-auto">
                                        <table className="w-full text-left text-sm">
                                            <thead>
                                                <tr className="border-b border-stone-200">
                                                    <th className="p-2">원본 줄</th>
                                                    <th className="p-2">항목</th>
                                                    <th className="p-2">원본 값</th>
                                                    <th className="p-2">안내·처리 이유</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {group.rows.map((row, index) => (
                                                    <tr
                                                        key={`${row.line}-${index}`}
                                                        className="border-b border-stone-100"
                                                    >
                                                        <td className="p-2">{row.line}</td>
                                                        <td className="whitespace-pre-wrap p-2">{row.label}</td>
                                                        <td className="whitespace-pre-wrap p-2">{row.value}</td>
                                                        <td className="whitespace-pre-wrap p-2">
                                                            {row.note || "—"}
                                                        </td>
                                                    </tr>
                                                ))}
                                            </tbody>
                                        </table>
                                    </div>
                                )}
                            </section>
                        ))}

                        {notes.length > 0 && (
                            <section className="space-y-2">
                                <h2 className="font-semibold">확인할 안내</h2>
                                {notes.map((note, index) => (
                                    <p key={index} className="whitespace-pre-wrap text-sm text-stone-700">
                                        {note}
                                    </p>
                                ))}
                            </section>
                        )}
                    </div>
                )}
            </section>

            <form onSubmit={submit} className="space-y-4 rounded-2xl bg-white p-6">
                <div className="grid gap-4 sm:grid-cols-2">
                    <label>
                        정산 시작일
                        <input type="date" className={field} value={form.period_start} onChange={(e) => setForm({ ...form, period_start: e.target.value })} />
                        {missingMessage("period_start") && (
                            <span className="mt-1 block text-sm text-stone-700">
                                {missingMessage("period_start")}
                            </span>
                        )}
                    </label>
                    <label>
                        정산 종료일
                        <input type="date" className={field} value={form.period_end} onChange={(e) => setForm({ ...form, period_end: e.target.value })} />
                        {missingMessage("period_end") && (
                            <span className="mt-1 block text-sm text-stone-700">
                                {missingMessage("period_end")}
                            </span>
                        )}
                    </label>
                </div>

                <div className="grid gap-4 sm:grid-cols-2">
                    {AMOUNTS.map(({ key, label, hint }) => (
                        <label key={key} className="block">
                            {label}
                            <input className={field} inputMode="decimal" value={form[key]} onChange={(e) => setForm({ ...form, [key]: e.target.value })} />
                            <span className="mt-1 block text-sm text-stone-600">{hint}</span>
                            {missingMessage(key) && (
                                <span className="mt-1 block text-sm text-stone-700">
                                    {missingMessage(key)}
                                </span>
                            )}
                        </label>
                    ))}
                </div>

                <fieldset className="space-y-2">
                    <legend className="font-semibold">정산서 공제 항목 (적혀 있으면)</legend>
                    {form.deductions.map((d, i) => (
                        <div key={i} className="grid gap-2 sm:grid-cols-3">
                            <input className={field} placeholder="항목 이름" value={d.name} onChange={(e) => setDed(i, { name: e.target.value })} />
                            <input className={field} placeholder="금액 (원)" inputMode="decimal" value={d.amount} onChange={(e) => setDed(i, { amount: e.target.value })} />
                            <button
                                type="button"
                                className={secondary}
                                onClick={() => setForm((f) => ({ ...f, deductions: f.deductions.filter((_, j) => j !== i) }))}
                            >
                                삭제
                            </button>
                        </div>
                    ))}
                    <button
                        type="button"
                        className={secondary}
                        onClick={() => setForm((f) => ({ ...f, deductions: [...f.deductions, { name: "", amount: "" }] }))}
                    >
                        공제 항목 추가
                    </button>
                </fieldset>

                <label className="block">
                    작가지급액 (원)
                    <input
                        className={field}
                        inputMode="decimal"
                        value={form.reported_payout}
                        onChange={(e) => setForm({ ...form, reported_payout: e.target.value })}
                    />
                    <span className="mt-1 block text-sm text-stone-600">필수. 원천징수 뒤 실제로 받는 금액입니다.</span>
                    {missingMessage("reported_payout") && (
                        <span className="mt-1 block text-sm text-stone-700">
                            {missingMessage("reported_payout")}
                        </span>
                    )}
                </label>
                <button type="submit" className={primary}>
                    정산서 저장
                </button>
                {message && <p role="status">{message}</p>}
            </form>

            <section className="space-y-3 rounded-2xl bg-white p-6">
                <h2 className="text-lg font-semibold">저장한 정산서</h2>
                {saved.length === 0 && <p className="text-stone-600">아직 없습니다.</p>}
                {saved.map((s) => (
                    <div key={s.id} className="flex flex-wrap items-center justify-between gap-2 border-t border-stone-200 pt-3">
                        <p>
                            {s.period_start} ~ {s.period_end} · 매출액 {won(s.gross)}
                            {s.reported_settlement != null && <> · 정산액 {won(s.reported_settlement)}</>}
                            {s.reported_withholding != null && <> · 원천징수 {won(s.reported_withholding)}</>} · 작가지급액{" "}
                            {won(s.reported_payout)}
                        </p>
                        <button type="button" className={secondary} onClick={() => remove(s.id)}>
                            삭제
                        </button>
                    </div>
                ))}
                {saved.length > 0 && (
                    <Link className={primary + " inline-block"} href={`/results?id=${id}`}>
                        대조 결과 보기
                    </Link>
                )}
            </section>
        </>
    );
}

export default function StatementsPage() {
    return (
        <main className="min-h-screen bg-stone-100 px-5 py-10 text-stone-900">
            <div className="mx-auto max-w-3xl space-y-5">
                <Link href="/" className="font-bold text-teal-900">
                    오픈북
                </Link>
                <Suspense>
                    <StatementsInner />
                </Suspense>
            </div>
        </main>
    );
}
