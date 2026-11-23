"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";
import {
  api,
  CHOICES,
  errorText,
  field,
  MONEY,
  primary,
  RATE,
  secondary,
  TERM_LABELS,
  type Deduction,
  type Term,
  type TermsResponse,
} from "../../lib/api";

const REQUIRED = ["mg_amount", "mg_recoup", "rs_rate", "revenue_base", "deductions"];
const STATUS_LABEL = { extracted: "추출됨", not_found: "찾지 못함", user_input: "직접 입력" };

type DedDraft = { name: string; kind: "rate" | "amount"; num: string };
type Draft = { text: string; deductions: DedDraft[]; confirmed: boolean };

function toDraft(t: Term): Draft {
  const ded = Array.isArray(t.value) && t.key === "deductions" ? (t.value as Deduction[]) : [];
  return {
    text: typeof t.value === "string" ? t.value : "",
    deductions: ded.map((d) => ({
      name: d.name,
      kind: d.rate != null ? "rate" : "amount",
      num: (d.rate ?? d.amount ?? "") as string,
    })),
    confirmed: t.confirmed,
  };
}

function draftValue(key: string, d: Draft): unknown {
  if (key === "deductions") {
    return d.deductions.map((x) =>
      x.kind === "rate" ? { name: x.name.trim(), rate: x.num.trim(), amount: null } : { name: x.name.trim(), rate: null, amount: x.num.trim() },
    );
  }
  return d.text.trim() || null;
}

function sameValue(a: unknown, b: unknown) {
  return JSON.stringify(a ?? null) === JSON.stringify(b ?? null);
}

function problem(key: string, value: unknown): string {
  if (key === "deductions") {
    for (const d of value as Deduction[]) {
      if (!d.name) return "공제 항목 이름을 입력해 주세요.";
      if (d.rate != null && !RATE.test(d.rate)) return "공제 비율은 0~1로 입력해 주세요. 예: 10%는 0.1";
      if (d.amount != null && !MONEY.test(d.amount)) return "공제 금액은 쉼표 없이 숫자로 입력해 주세요.";
    }
    return "";
  }
  if (value == null) return "값을 입력해 주세요.";
  if (key === "mg_amount" && !MONEY.test(value as string)) return "금액을 쉼표 없이 숫자로 입력해 주세요.";
  if (key === "rs_rate" && !RATE.test(value as string)) return "비율을 0~1로 입력해 주세요. 예: 60%는 0.6";
  return "";
}

function TermsInner() {
  const id = useSearchParams().get("id") ?? "";
  const [data, setData] = useState<TermsResponse | null>(null);
  const [drafts, setDrafts] = useState<Record<string, Draft>>({});
  const [message, setMessage] = useState("");
  const [saving, setSaving] = useState(false);

  const load = useCallback((res: TermsResponse) => {
    setData(res);
    setDrafts(Object.fromEntries(res.terms.map((t) => [t.key, toDraft(t)])));
  }, []);

  useEffect(() => {
    if (!id) return;
    api<TermsResponse>(`/contracts/${id}/terms`).then(load, (e) => setMessage(errorText(e)));
  }, [id, load]);

  const set = (key: string, patch: Partial<Draft>) =>
    setDrafts((prev) => ({ ...prev, [key]: { ...prev[key], ...patch } }));

  async function save() {
    if (!data) return;
    const updates = [];
    for (const t of data.terms) {
      const d = drafts[t.key];
      const tiered = t.key === "rs_rate" && Array.isArray(t.value);
      const value = tiered ? t.value : draftValue(t.key, d);
      // 찾지 못한 조건을 비워 둔 채면 바꾸지 않는다 (공제 '없음'은 체크해야 저장)
      const empty = value == null || (Array.isArray(value) && value.length === 0);
      const untouched = t.status === "not_found" && empty && !d.confirmed;
      const changed = !tiered && !untouched && !sameValue(value, t.value);
      if (!changed && d.confirmed === t.confirmed) continue;
      if (changed || d.confirmed) {
        const why = tiered ? "" : problem(t.key, value);
        if (why) {
          setMessage(`${TERM_LABELS[t.key]}: ${why}`);
          return;
        }
      }
      updates.push({ key: t.key, value: changed ? value : null, confirmed: d.confirmed });
    }
    if (!updates.length) {
      setMessage("바뀐 내용이 없습니다.");
      return;
    }
    setSaving(true);
    try {
      const res = await api<TermsResponse>(`/contracts/${id}/terms`, {
        method: "PUT",
        body: JSON.stringify({ terms: updates }),
      });
      load(res);
      setMessage(res.all_confirmed ? "저장했습니다. 이제 정산서를 입력할 수 있습니다." : "저장했습니다.");
    } catch (e) {
      setMessage(errorText(e));
    } finally {
      setSaving(false);
    }
  }

  if (!id) return <p className="rounded-2xl bg-white p-6">계약서를 먼저 선택해 주세요.</p>;
  if (!data) return <p role="status" className="rounded-2xl bg-white p-6">{message || "불러오는 중…"}</p>;

  return (
    <>
      <section className="space-y-2 rounded-2xl bg-white p-6">
        <h1 className="text-2xl font-bold">조건 확인·수정</h1>
        <p>계약서에서 찾은 정산 조건입니다. 원문과 비교해 값을 확인하고 체크해 주세요.</p>
        <p>
          확인이 필요한 필수 조건 ·{" "}
          {data.unconfirmed_required.map((k) => TERM_LABELS[k] ?? k).join(", ") || "없음"}
        </p>
      </section>

      {data.terms.map((t) => {
        const d = drafts[t.key];
        if (!d) return null;
        const tiered = t.key === "rs_rate" && Array.isArray(t.value);
        return (
          <article key={t.key} className="space-y-3 rounded-2xl bg-white p-6">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-lg font-semibold">
                {TERM_LABELS[t.key] ?? t.key}
                {REQUIRED.includes(t.key) && <span className="ml-2 text-sm text-stone-600">필수</span>}
              </h2>
              <span className="rounded border border-stone-300 px-2 py-1 text-sm">{STATUS_LABEL[t.status]}</span>
            </div>
            {data.unconfirmed_required.includes(t.key) && <p className="font-medium">확인해 주세요</p>}
            {t.status === "not_found" && (
              <p className="text-sm text-stone-600">
                계약서에서 이 조건을 찾지 못했습니다. 표준·일반 조건과 같다는 뜻이 아닙니다.
              </p>
            )}

            {tiered ? (
              <p>구간별 RS는 아직 계산하지 않습니다. 대조 결과에 계산 불가로 표시됩니다.</p>
            ) : t.key === "deductions" ? (
              <div className="space-y-3">
                {d.deductions.length === 0 && <p className="text-sm text-stone-600">공제 항목 없음</p>}
                {d.deductions.map((x, i) => {
                  const upd = (patch: Partial<DedDraft>) =>
                    set(t.key, { deductions: d.deductions.map((y, j) => (i === j ? { ...y, ...patch } : y)) });
                  return (
                    <fieldset key={i} className="grid gap-2 rounded-lg border border-stone-300 p-3 sm:grid-cols-3">
                      <label>
                        이름
                        <input className={field} value={x.name} onChange={(e) => upd({ name: e.target.value })} />
                      </label>
                      <label>
                        방식
                        <select className={field} value={x.kind} onChange={(e) => upd({ kind: e.target.value as DedDraft["kind"] })}>
                          <option value="rate">비율 (0~1)</option>
                          <option value="amount">금액 (원)</option>
                        </select>
                      </label>
                      <label>
                        값
                        <input className={field} inputMode="decimal" value={x.num} onChange={(e) => upd({ num: e.target.value })} />
                      </label>
                      <button
                        type="button"
                        className={secondary}
                        onClick={() => set(t.key, { deductions: d.deductions.filter((_, j) => j !== i) })}
                      >
                        이 항목 삭제
                      </button>
                    </fieldset>
                  );
                })}
                <button
                  type="button"
                  className={secondary}
                  onClick={() => set(t.key, { deductions: [...d.deductions, { name: "", kind: "rate", num: "" }] })}
                >
                  공제 항목 추가
                </button>
              </div>
            ) : CHOICES[t.key] ? (
              <select className={field} value={d.text} onChange={(e) => set(t.key, { text: e.target.value })}>
                <option value="">선택해 주세요</option>
                {Object.entries(CHOICES[t.key]).map(([v, label]) => (
                  <option key={v} value={v}>
                    {label}
                  </option>
                ))}
              </select>
            ) : (
              <label className="block">
                값
                <input
                  className={field}
                  inputMode={t.key === "mg_amount" || t.key === "rs_rate" ? "decimal" : "text"}
                  value={d.text}
                  onChange={(e) => set(t.key, { text: e.target.value })}
                />
                {t.key === "mg_amount" && <span className="text-sm text-stone-600">원 단위, 쉼표 없이</span>}
                {t.key === "rs_rate" && <span className="text-sm text-stone-600">0~1. 예: 60%는 0.6</span>}
              </label>
            )}

            {t.quote ? (
              <blockquote className="whitespace-pre-wrap break-words border-l-2 border-stone-300 pl-3">
                <span className="mb-1 block text-sm font-medium">근거 조항 · {t.source_clause_id}</span>
                {t.quote}
              </blockquote>
            ) : (
              <p className="text-sm text-stone-600">연결된 근거 조항이 없습니다.</p>
            )}

            <label className="flex items-start gap-2 border-t border-stone-200 pt-3">
              <input
                type="checkbox"
                className="mt-1"
                checked={d.confirmed}
                onChange={(e) => set(t.key, { confirmed: e.target.checked })}
              />
              계약서와 이 값을 확인했습니다.
            </label>
          </article>
        );
      })}

      <section className="flex flex-wrap items-center gap-3 rounded-2xl bg-white p-6">
        <button type="button" className={primary} disabled={saving} onClick={save}>
          {saving ? "저장 중…" : "저장"}
        </button>
        {data.all_confirmed && (
          <Link className={primary} href={`/statements?id=${id}`}>
            정산서 입력으로
          </Link>
        )}
        {message && <p role="status" className="w-full">{message}</p>}
      </section>
    </>
  );
}

export default function TermsPage() {
  return (
    <main className="min-h-screen bg-stone-100 px-5 py-10 text-stone-900">
      <div className="mx-auto max-w-3xl space-y-5">
        <Link href="/" className="font-bold text-teal-900">
          오픈북
        </Link>
        <Suspense>
          <TermsInner />
        </Suspense>
      </div>
    </main>
  );
}
