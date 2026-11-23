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
  won,
  type StatementBody,
  type StatementDraft,
  type StatementOut,
} from "../../lib/api";

const EMPTY: StatementBody = { period_start: "", period_end: "", gross: "", deductions: [], reported_payout: "" };

function StatementsInner() {
  const id = useSearchParams().get("id") ?? "";
  const [form, setForm] = useState<StatementBody>(EMPTY);
  const [paste, setPaste] = useState("");
  const [saved, setSaved] = useState<StatementOut[]>([]);
  const [message, setMessage] = useState("");
  const [notes, setNotes] = useState<string[]>([]);

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
    try {
      const d = await api<StatementDraft>(`/contracts/${id}/statements/paste`, {
        method: "POST",
        body: JSON.stringify({ text: paste }),
      });
      setForm({
        period_start: d.period_start ?? "",
        period_end: d.period_end ?? "",
        gross: d.gross ?? "",
        deductions: d.deductions ?? [],
        reported_payout: d.reported_payout ?? "",
      });
      setNotes(d.warnings ?? []);
      setMessage("붙여넣은 표에서 읽은 값을 채웠습니다. 정산서와 비교해 확인해 주세요.");
    } catch (e) {
      setMessage(errorText(e));
    }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!form.period_start || !form.period_end) return setMessage("정산 기간을 입력해 주세요.");
    if (form.period_end < form.period_start) return setMessage("정산 기간의 끝이 시작보다 앞입니다.");
    if (!MONEY.test(form.gross) || !MONEY.test(form.reported_payout))
      return setMessage("총매출과 지급액을 쉼표 없이 숫자로 입력해 주세요.");
    if (form.deductions.some((d) => !d.name.trim() || !MONEY.test(d.amount)))
      return setMessage("공제 항목의 이름과 금액을 확인해 주세요.");
    try {
      await api(`/contracts/${id}/statements`, { method: "POST", body: JSON.stringify(form) });
      setForm(EMPTY);
      setPaste("");
      setNotes([]);
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
        {notes.map((n) => (
          <p key={n} className="text-sm text-stone-600">
            {n}
          </p>
        ))}
      </section>

      <form onSubmit={submit} className="space-y-4 rounded-2xl bg-white p-6">
        <div className="grid gap-4 sm:grid-cols-2">
          <label>
            정산 시작일
            <input type="date" className={field} value={form.period_start} onChange={(e) => setForm({ ...form, period_start: e.target.value })} />
          </label>
          <label>
            정산 종료일
            <input type="date" className={field} value={form.period_end} onChange={(e) => setForm({ ...form, period_end: e.target.value })} />
          </label>
        </div>
        <label className="block">
          정산서 총매출 (원)
          <input className={field} inputMode="decimal" value={form.gross} onChange={(e) => setForm({ ...form, gross: e.target.value })} />
        </label>

        <fieldset className="space-y-2">
          <legend className="font-semibold">정산서 공제 항목</legend>
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
          정산서에 적힌 지급액 (원)
          <input
            className={field}
            inputMode="decimal"
            value={form.reported_payout}
            onChange={(e) => setForm({ ...form, reported_payout: e.target.value })}
          />
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
              {s.period_start} ~ {s.period_end} · 총매출 {won(s.gross)} · 지급액 {won(s.reported_payout)}
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
