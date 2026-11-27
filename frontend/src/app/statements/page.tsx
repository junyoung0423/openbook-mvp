"use client";

import { Plus, Trash2 } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { Card } from "../../components/Card";
import { InfoPanel } from "../../components/InfoPanel";
import { MoneyInput } from "../../components/MoneyInput";
import { api, errorText, MONEY, SIGNED_MONEY, won, type StatementBody, type StatementDraft, type StatementOut } from "../../lib/api";
import { periodTitle } from "../../lib/format";
import { buttonClass, fieldClass } from "../../lib/ui";

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

// 정산서 금액 칸. "필수"는 매출액·작가지급액·기간에만 붙인다. 매출액·회사입금액·정산액은 음수도 받는다(SIGNED_MONEY).
const AMOUNTS: {
  key: "gross" | "net_revenue" | "reported_settlement" | "reported_withholding";
  label: string;
  required: boolean;
  negative: boolean;
  hint: string;
}[] = [
  { key: "gross", label: "매출액", required: true, negative: true, hint: "환불이 많은 달은 음수(-)도 됩니다." },
  { key: "net_revenue", label: "회사입금액", required: false, negative: true, hint: "순매출 기준 계약이면 필요합니다." },
  { key: "reported_settlement", label: "정산액", required: false, negative: true, hint: "작가 몫. 적혀 있으면 계약서 기준과 대조합니다." },
  { key: "reported_withholding", label: "원천징수", required: false, negative: false, hint: "적혀 있으면 3.3% 계산과 대조합니다." },
];

const toBody = (f: Form): StatementBody => ({
  ...f,
  net_revenue: f.net_revenue || null,
  reported_settlement: f.reported_settlement || null,
  reported_withholding: f.reported_withholding || null,
});

function Tabs({ mode, onChange }: { mode: "paste" | "manual"; onChange: (m: "paste" | "manual") => void }) {
  return (
    <div role="tablist" aria-label="입력 방법" className="flex rounded-tabbar bg-line-soft p-[3px] text-[13px] font-[650]">
      {(
        [
          ["paste", "표 붙여넣기 · 추천"],
          ["manual", "직접 입력"],
        ] as const
      ).map(([m, text]) => (
        <button
          key={m}
          type="button"
          role="tab"
          aria-selected={mode === m}
          onClick={() => onChange(m)}
          className={`min-h-[38px] rounded-tab px-3.5 ${mode === m ? "bg-card font-bold text-ink shadow-tab" : "font-semibold text-ink-2"}`}
        >
          {text}
        </button>
      ))}
    </div>
  );
}

function Field({ label, required, hint, note, children }: { label: string; required?: boolean; hint?: string; note?: string; children: ReactNode }) {
  return (
    <label className="block text-[13px] font-semibold">
      {label} {required && <span className="font-medium text-muted">필수</span>}
      {children}
      {hint && <span className="mt-1.5 block text-fine font-medium text-muted">{hint}</span>}
      {note && <span className="mt-1 block text-small font-medium text-ink-2">{note}</span>}
    </label>
  );
}

function StatementsInner() {
  const id = useSearchParams().get("id") ?? "";
  const [form, setForm] = useState<Form>(EMPTY);
  const [paste, setPaste] = useState("");
  const [mode, setMode] = useState<"paste" | "manual">("paste");
  const [saved, setSaved] = useState<StatementOut[]>([]);
  const [message, setMessage] = useState("");
  const [notes, setNotes] = useState<string[]>([]);
  const [pasteResult, setPasteResult] = useState<StatementDraft | null>(null);
  const formCard = useRef<HTMLElement>(null);
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
      // 채워진 폼으로 데려간다 (움직임을 줄인 설정이면 그대로 이동)
      const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      requestAnimationFrame(() => formCard.current?.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" }));
    } catch (e) {
      setMessage(errorText(e));
    }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!form.period_start || !form.period_end) return setMessage("정산 기간을 입력해 주세요.");
    if (form.period_end < form.period_start) return setMessage("정산 기간의 끝이 시작보다 앞입니다.");
    if (!SIGNED_MONEY.test(form.gross) || !MONEY.test(form.reported_payout)) return setMessage("매출액과 작가지급액을 숫자로 입력해 주세요.");
    if (
      (form.net_revenue && !SIGNED_MONEY.test(form.net_revenue)) ||
      (form.reported_settlement && !SIGNED_MONEY.test(form.reported_settlement)) ||
      (form.reported_withholding && !MONEY.test(form.reported_withholding))
    )
      return setMessage("회사입금액·정산액·원천징수는 비워 두거나 숫자로 입력해 주세요.");
    if (form.deductions.some((d) => !d.name.trim() || !MONEY.test(d.amount))) return setMessage("공제 항목의 이름과 금액을 확인해 주세요.");
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

    const missing =
      (
        pasteResult as StatementDraft & {
          missing?: string[];
        }
      ).missing ?? [];

    const missingKey = key === "period_start" || key === "period_end" ? "period" : key;

    if (!missing.includes(missingKey) || form[key] !== "") return "";

    return "붙여넣은 표에서 찾지 못했습니다. 정산서를 확인해 직접 입력해 주세요.";
  }
  const setDed = (i: number, patch: Partial<{ name: string; amount: string }>) =>
    setForm((f) => ({ ...f, deductions: f.deductions.map((d, j) => (i === j ? { ...d, ...patch } : d)) }));

  if (!id)
    return (
      <InfoPanel title="계약서를 먼저 선택해 주세요.">
        <Link className={buttonClass("primary")} href="/">
          계약서 올리러 가기
        </Link>
      </InfoPanel>
    );

  const title = form.period_start && form.period_end ? `${periodTitle(form.period_start, form.period_end)} 정산서` : "이 달 정산서";
  const dateInput = "num mt-1.5 block min-h-[46px] w-full rounded-field border border-field bg-card px-3.5 text-[15px] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent";

  return (
    <div className="flex flex-wrap items-start gap-4">
      <div className="flex min-w-0 flex-[999_1_520px] flex-col gap-4">
        <Card className="flex flex-col gap-3.5 !px-5 !py-6 md:!px-[26px]">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-title font-[750]">정산서 입력</h2>
            <Tabs mode={mode} onChange={setMode} />
          </div>
          {mode === "paste" ? (
            <>
              <p className="text-sm leading-[1.6] text-ink-2">
                플랫폼 정산서의 표를 통째로 복사해 붙여넣으면, 아래 칸을 자동으로 채워 드려요. 채운 값은 꼭 정산서와 비교해 주세요.
              </p>
              <textarea
                aria-label="정산서 표 붙여넣기"
                rows={6}
                value={paste}
                onChange={(e) => setPaste(e.target.value)}
                className="w-full rounded-tile border border-field bg-[#f9fafd] px-4 py-3.5 font-mono text-[13.5px] leading-[1.6] text-[#2a2e3d] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
              />
              <div className="flex flex-wrap items-center gap-2.5">
                <button type="button" disabled={!paste.trim()} onClick={readPaste} className={buttonClass("dark")}>
                  표에서 값 읽기
                </button>
                {pasteResult && (
                  <span role="status" className="text-sm font-[650] text-accent">
                    {pasteResult.rows ? `${pasteResult.rows.length}줄을 읽어 아래 칸에 채웠어요` : "읽은 값을 아래 칸에 채웠어요"}
                  </span>
                )}
              </div>
              {pasteResult && (
                <div className="flex flex-col gap-4">
                  <p className="text-sm text-ink-2">표를 읽은 시점의 결과입니다. 아래 입력 칸에서 원본과 비교해 확인해 주세요.</p>

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
                    <section key={group.title} className="flex flex-col gap-2">
                      <h3 className="text-sm font-bold">{group.title}</h3>

                      {group.rows.length === 0 ? (
                        <p className="text-sm text-muted">없습니다.</p>
                      ) : (
                        <div className="overflow-x-auto rounded-tile border border-line">
                          <table className="w-full border-collapse text-left text-[13px]">
                            <thead>
                              <tr className="bg-quote text-muted">
                                <th scope="col" className="px-3 py-2 font-semibold">
                                  원본 줄
                                </th>
                                <th scope="col" className="px-3 py-2 font-semibold">
                                  항목
                                </th>
                                <th scope="col" className="px-3 py-2 font-semibold">
                                  원본 값
                                </th>
                                <th scope="col" className="px-3 py-2 font-semibold">
                                  안내·처리 이유
                                </th>
                              </tr>
                            </thead>
                            <tbody>
                              {group.rows.map((row, index) => (
                                <tr key={`${row.line}-${index}`} className="border-t border-line-soft">
                                  <td className="num px-3 py-2">{row.line}</td>
                                  <td className="whitespace-pre-wrap px-3 py-2">{row.label}</td>
                                  <td className="num whitespace-pre-wrap px-3 py-2">{row.value}</td>
                                  <td className="whitespace-pre-wrap px-3 py-2 text-ink-2">{row.note || "—"}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      )}
                    </section>
                  ))}

                  {notes.length > 0 && (
                    <section className="flex flex-col gap-2">
                      <h3 className="text-sm font-bold">확인할 안내</h3>
                      {notes.map((note, index) => (
                        <p key={index} className="whitespace-pre-wrap text-sm text-ink-2">
                          {note}
                        </p>
                      ))}
                    </section>
                  )}
                </div>
              )}
            </>
          ) : (
            <p className="text-sm leading-[1.6] text-ink-2">정산서에 적힌 순서대로 아래 칸을 채워 주세요. 적혀 있지 않은 칸은 비워 둬도 됩니다.</p>
          )}
        </Card>

        <Card className="!px-5 !py-6 md:!px-[26px]" ref={formCard}>
          <form onSubmit={submit} className="flex flex-col gap-4">
            <h3 className="text-[17px] font-[750]">{title}</h3>
            <div className="grid gap-3.5 md:grid-cols-2">
              <Field label="정산 시작일" required note={missingMessage("period_start")}>
                <input type="date" className={dateInput} value={form.period_start} onChange={(e) => setForm({ ...form, period_start: e.target.value })} />
              </Field>
              <Field label="정산 종료일" required note={missingMessage("period_end")}>
                <input type="date" className={dateInput} value={form.period_end} onChange={(e) => setForm({ ...form, period_end: e.target.value })} />
              </Field>
              {AMOUNTS.map(({ key, label, required, negative, hint }) => (
                <Field key={key} label={label} required={required} hint={hint} note={missingMessage(key)}>
                  <MoneyInput value={form[key]} allowNegative={negative} onChange={(v) => setForm({ ...form, [key]: v })} />
                </Field>
              ))}
            </div>

            <fieldset className="flex flex-col gap-2 rounded-field border border-line px-4 py-3.5">
              <legend className="px-1.5 text-[13px] font-[650]">
                정산서 공제 항목 <span className="font-medium text-muted">적혀 있으면</span>
              </legend>
              {form.deductions.map((d, i) => (
                <div key={i} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-2 md:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)_auto]">
                  <input
                    aria-label="공제 항목 이름"
                    className={`${fieldClass} !mt-0 !min-h-[42px] !text-sm max-md:col-span-2`}
                    placeholder="항목 이름"
                    value={d.name}
                    onChange={(e) => setDed(i, { name: e.target.value })}
                  />
                  <MoneyInput aria-label="공제 금액" className="!mt-0 !min-h-[42px]" value={d.amount} onChange={(v) => setDed(i, { amount: v })} />
                  <button
                    type="button"
                    aria-label={`${d.name.trim() || `공제 항목 ${i + 1}`} 삭제`}
                    onClick={() => setForm((f) => ({ ...f, deductions: f.deductions.filter((_, j) => j !== i) }))}
                    className="grid size-11 place-items-center rounded-btn text-muted hover:bg-line-soft"
                  >
                    <Trash2 size={16} aria-hidden />
                  </button>
                </div>
              ))}
              <button
                type="button"
                onClick={() => setForm((f) => ({ ...f, deductions: [...f.deductions, { name: "", amount: "" }] }))}
                className="inline-flex min-h-11 items-center gap-1.5 self-start rounded-btn border border-dashed border-locked px-3 text-[13px] font-[650] text-accent"
              >
                <Plus size={14} aria-hidden />
                공제 항목 추가
              </button>
            </fieldset>

            <label className="block rounded-tile bg-quote px-[18px] py-4 text-sm font-bold">
              작가지급액 <span className="font-medium text-muted">필수 · 원천징수 뒤 실제로 받는 금액</span>
              <MoneyInput size="lg" className="!mt-2" value={form.reported_payout} onChange={(v) => setForm({ ...form, reported_payout: v })} />
              {missingMessage("reported_payout") && <span className="mt-1.5 block text-small font-medium text-ink-2">{missingMessage("reported_payout")}</span>}
            </label>

            <div className="flex flex-wrap items-center justify-end gap-x-4 gap-y-2">
              {message && (
                <p role="status" className="mr-auto text-sm font-medium text-ink-2">
                  {message}
                </p>
              )}
              <button type="submit" className={`${buttonClass("primary")} !min-h-12 !px-[26px]`}>
                이 달 정산서 저장
              </button>
            </div>
          </form>
        </Card>
      </div>

      <aside aria-label="저장한 정산서" className="flex min-w-0 flex-[1_1_280px] flex-col gap-3 rounded-card bg-card p-[22px] shadow-card">
        <h3 className="text-base font-[750]">
          저장한 정산서 <span className="num font-medium text-muted">{saved.length}건</span>
        </h3>
        {saved.length === 0 && <p className="text-sm text-muted">아직 없습니다.</p>}
        <ul className="flex flex-col gap-2">
          {saved.map((s) => {
            const name = periodTitle(s.period_start, s.period_end);
            return (
              <li key={s.id} className="flex items-center gap-2.5 rounded-field border border-line-soft px-3.5 py-3">
                <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                  <span className="text-sm font-bold">{name}</span>
                  <span className="num text-fine text-muted">
                    매출 {won(s.gross)} · 지급 {won(s.reported_payout)}
                  </span>
                </span>
                <button
                  type="button"
                  aria-label={`${name} 정산서 삭제`}
                  onClick={() => remove(s.id)}
                  className="grid size-11 shrink-0 place-items-center rounded-btn text-muted hover:bg-line-soft"
                >
                  <Trash2 size={16} aria-hidden />
                </button>
              </li>
            );
          })}
        </ul>
        {saved.length > 0 && (
          <Link className={`${buttonClass("dark")} !min-h-12 !text-[15px]`} href={`/results?id=${id}`}>
            대조 결과 보기 →
          </Link>
        )}
      </aside>
    </div>
  );
}

export default function StatementsPage() {
  return (
    <Suspense>
      <StatementsInner />
    </Suspense>
  );
}
