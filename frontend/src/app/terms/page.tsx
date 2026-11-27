"use client";

import { Plus, Trash2 } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState, type ReactNode } from "react";
import { Card } from "../../components/Card";
import { InfoPanel } from "../../components/InfoPanel";
import { MoneyInput } from "../../components/MoneyInput";
import { ProcessingState } from "../../components/Spinner";
import { RateInput } from "../../components/RateInput";
import { useContract, useContracts } from "../../components/ShellContext";
import { SourceQuote } from "../../components/SourceQuote";
import { StatusBadge } from "../../components/StatusBadge";
import { api, CHOICES, errorText, MONEY, RATE, TERM_LABELS, type Clause, type ContractOut, type Deduction, type Term, type TermsResponse } from "../../lib/api";
import { buttonClass, fieldClass } from "../../lib/ui";

const REQUIRED = ["mg_amount", "mg_recoup", "rs_rate", "revenue_base", "deductions"];
const OPTIONAL = ["mg_pay_date", "mg_carryover", "settlement_cycle", "payment_day"];

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
      if (d.rate != null && !RATE.test(d.rate)) return "공제 비율은 0~100% 사이로 입력해 주세요.";
      if (d.amount != null && !MONEY.test(d.amount)) return "공제 금액은 숫자로 입력해 주세요.";
    }
    return "";
  }
  if (value == null) return "값을 입력해 주세요.";
  if (key === "mg_amount" && !MONEY.test(value as string)) return "금액은 숫자로 입력해 주세요.";
  if (key === "rs_rate" && !RATE.test(value as string)) return "비율은 0~100% 사이로 입력해 주세요.";
  return "";
}

// ---------------------------------------------------------------- 표시용 도우미 (값을 바꾸지 않고 모양만 정한다)

const isTiered = (t: Term) => t.key === "rs_rate" && Array.isArray(t.value);

function isEmpty(t: Term, d: Draft) {
  if (isTiered(t)) return false;
  return t.key === "deductions" ? d.deductions.length === 0 : d.text.trim() === "";
}

// `찾지 못함`이고 값이 비어 있으면 확인할 수 없다. 단 공제 항목은 빈 목록 + 확인 = "공제 없음"이라는 뜻이라 막지 않는다.
const blocked = (t: Term, d: Draft) => t.status === "not_found" && t.key !== "deductions" && isEmpty(t, d);

// 사용자가 값을 고치면 상태 라벨이 `직접 입력`으로 바뀐다
const blank = (v: unknown) => v == null || (Array.isArray(v) && v.length === 0);

function shownStatus(t: Term, d: Draft): Term["status"] {
  if (isTiered(t)) return t.status;
  const now = draftValue(t.key, d);
  // 비어 있는 공제 목록([])과 서버의 값 없음(null)은 같은 "값 없음"이다
  return (blank(now) && blank(t.value)) || sameValue(now, t.value) ? t.status : "user_input";
}

// ---------------------------------------------------------------- 작은 부품

function ConfirmToggle({
  checked,
  locked,
  label,
  onChange,
}: {
  checked: boolean;
  locked: boolean;
  label: string;
  onChange: (checked: boolean) => void;
}) {
  const look = locked
    ? "cursor-not-allowed border-line text-muted"
    : checked
      ? "cursor-pointer border-accent bg-accent-soft text-accent"
      : "cursor-pointer border-field bg-card text-ink";
  return (
    <label className={`flex min-h-11 items-center gap-2.5 self-start rounded-btn border px-4 text-sm font-[650] has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-accent ${look}`}>
      <input
        type="checkbox"
        className="size-[18px] accent-accent"
        checked={checked && !locked}
        disabled={locked}
        onChange={(e) => onChange(e.target.checked)}
      />
      <span>{label}</span>
    </label>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="flex flex-col text-small text-muted">
      {label}
      {children}
    </label>
  );
}

function ChoiceSelect({ termKey, value, onChange, label }: { termKey: string; value: string; onChange: (v: string) => void; label: string }) {
  return (
    <Field label={label}>
      <select className={`${fieldClass} text-ink`} value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">선택해 주세요</option>
        {Object.entries(CHOICES[termKey]).map(([v, text]) => (
          <option key={v} value={v}>
            {text}
          </option>
        ))}
      </select>
    </Field>
  );
}

function Quote({ t, clauseLabel }: { t: Term; clauseLabel: (id: string | null | undefined) => string }) {
  return t.quote ? (
    <SourceQuote label={clauseLabel(t.source_clause_id)} className="h-full">
      {t.quote}
    </SourceQuote>
  ) : (
    <SourceQuote label="근거 조항" prefix="" className="h-full">
      연결된 근거 조항이 없습니다.
    </SourceQuote>
  );
}

// 공제 항목: 줄마다 [이름 | 비율/금액 | 값 | 삭제]. 좁은 화면은 두 줄.
function Deductions({ d, onChange }: { d: Draft; onChange: (patch: Partial<Draft>) => void }) {
  const upd = (i: number, patch: Partial<DedDraft>) => onChange({ deductions: d.deductions.map((y, j) => (i === j ? { ...y, ...patch } : y)) });
  return (
    <div className="flex flex-col gap-2">
      {d.deductions.map((x, i) => (
        <div key={i} className="grid grid-cols-[auto_minmax(0,1fr)_auto] items-end gap-2 md:grid-cols-[minmax(0,1.4fr)_auto_minmax(0,1fr)_auto]">
          <label className="col-span-3 text-fine text-muted md:col-span-1">
            이름
            <input
              className={`${fieldClass} !min-h-[42px] !text-sm`}
              value={x.name}
              onChange={(e) => upd(i, { name: e.target.value })}
            />
          </label>
          <span role="group" aria-label="공제 방식" className="flex rounded-tabbar bg-line-soft p-[3px] text-[13px]">
            {(
              [
                ["rate", "비율"],
                ["amount", "금액"],
              ] as const
            ).map(([kind, text]) => (
              <button
                key={kind}
                type="button"
                aria-pressed={x.kind === kind}
                // 비율 "0.3"이 금액 "0.3원"으로 읽히지 않도록, 방식을 바꾸면 값을 비운다
                onClick={() => x.kind !== kind && upd(i, { kind, num: "" })}
                className={`min-h-[38px] rounded-tab px-3 ${x.kind === kind ? "bg-card font-bold text-ink shadow-tab" : "font-medium text-ink-2"}`}
              >
                {text}
              </button>
            ))}
          </span>
          <span className="block text-fine text-muted">
            <span className="sr-only">값</span>
            {x.kind === "rate" ? (
              <RateInput aria-label="공제 비율" value={x.num} onChange={(num) => upd(i, { num })} className="!mt-0" />
            ) : (
              <MoneyInput aria-label="공제 금액" value={x.num} onChange={(num) => upd(i, { num })} className="!mt-0" />
            )}
          </span>
          <button
            type="button"
            aria-label={`${x.name.trim() || "공제 항목"} 삭제`}
            onClick={() => onChange({ deductions: d.deductions.filter((_, j) => j !== i) })}
            className="grid size-11 place-items-center rounded-btn text-muted hover:bg-line-soft"
          >
            <Trash2 size={16} aria-hidden />
          </button>
        </div>
      ))}
      <button
        type="button"
        onClick={() => onChange({ deductions: [...d.deductions, { name: "", kind: "rate", num: "" }] })}
        className="inline-flex min-h-11 items-center gap-1.5 self-start rounded-btn border border-dashed border-locked px-3 text-[13px] font-[650] text-accent"
      >
        <Plus size={14} aria-hidden />
        공제 항목 추가
      </button>
    </div>
  );
}

// 필수 조건 카드: 왼쪽 = 이름 + 상태 라벨 + 입력 + 확인, 오른쪽 = 근거 원문. 좁으면 값 → 원문 순서로 쌓인다.
function RequiredCard({
  t,
  d,
  onChange,
  clauseLabel,
}: {
  t: Term;
  d: Draft;
  onChange: (patch: Partial<Draft>) => void;
  clauseLabel: (id: string | null | undefined) => string;
}) {
  const tiered = isTiered(t);
  const lock = blocked(t, d);
  const emptyNotFound = t.status === "not_found" && isEmpty(t, d);
  const confirmed = d.confirmed && !lock;
  const isDeductions = t.key === "deductions";
  const isSelect = !!CHOICES[t.key];
  const ownConfirm = emptyNotFound && isDeductions && !d.confirmed;
  const border = emptyNotFound && !d.confirmed ? "border-dashed border-dash-card" : confirmed ? "border-accent-line" : "border-transparent";

  let control: ReactNode;
  if (tiered) control = <p>구간별 RS는 아직 계산하지 않습니다. 대조 결과에 계산 불가로 표시됩니다.</p>;
  else if (isDeductions) control = <Deductions d={d} onChange={onChange} />;
  else if (isSelect) control = <ChoiceSelect termKey={t.key} label="값" value={d.text} onChange={(text) => onChange({ text })} />;
  else if (t.key === "rs_rate")
    control = (
      <Field label="값">
        <RateInput value={d.text} onChange={(text) => onChange({ text })} className="max-w-[200px]" />
      </Field>
    );
  else
    control = (
      <Field label="값">
        <MoneyInput value={d.text} onChange={(text) => onChange({ text })} />
      </Field>
    );

  const lockedLabel = isSelect ? "값을 고르면 확인할 수 있어요" : "값을 넣어야 확인할 수 있어요";
  const label = lock ? lockedLabel : confirmed ? "확인했습니다" : isDeductions && isEmpty(t, d) ? "공제 항목이 없는 것으로 확인했습니다" : "계약서와 이 값을 확인했습니다";

  return (
    <article className={`flex flex-wrap gap-5 rounded-card border-[1.5px] bg-card p-4 shadow-card md:px-6 md:py-[22px] ${border}`}>
      <div className="flex min-w-0 flex-[1_1_340px] flex-col gap-3">
        <div className="flex items-center justify-between gap-2">
          <h4 className="text-base font-bold">{TERM_LABELS[t.key] ?? t.key}</h4>
          <StatusBadge status={shownStatus(t, d)} />
        </div>
        {control}
        {emptyNotFound && (
          <p className="text-small leading-[1.55] text-ink-2">
            계약서에서 이 조건을 찾지 못했습니다. 표준·일반 조건과 같다는 뜻이 아닙니다.{" "}
            {isDeductions ? "공제가 없다면 그대로 확인하고, 있다면 항목을 추가해 주세요." : isSelect ? "계약서 문구를 보고 직접 골라 주세요." : "계약서 문구를 보고 직접 입력해 주세요."}
          </p>
        )}
        <ConfirmToggle checked={d.confirmed} locked={lock} label={ownConfirm ? "공제 항목이 없는 것으로 확인했습니다" : label} onChange={(confirmed) => onChange({ confirmed })} />
      </div>
      <div className="min-w-0 flex-[1_1_300px]">
        <Quote t={t} clauseLabel={clauseLabel} />
      </div>
    </article>
  );
}

// 참고 조건 카드: 평소엔 값 + 근거만 보이는 읽기 전용. "수정"을 누르면 입력칸과 확인 칸이 펼쳐진다.
function OptionalCard({
  t,
  d,
  editing,
  onToggleEdit,
  onChange,
  clauseLabel,
}: {
  t: Term;
  d: Draft;
  editing: boolean;
  onToggleEdit: () => void;
  onChange: (patch: Partial<Draft>) => void;
  clauseLabel: (id: string | null | undefined) => string;
}) {
  const isSelect = !!CHOICES[t.key];
  const lock = blocked(t, d);
  const shown = isSelect ? (CHOICES[t.key][d.text] ?? d.text) : d.text;
  const name = TERM_LABELS[t.key] ?? t.key;
  return (
    <article className={`flex flex-col gap-2 rounded-tile bg-card px-5 py-[18px] shadow-card ${editing ? "ring-1 ring-accent-line" : ""}`}>
      <div className="flex items-center justify-between gap-2">
        <h4 className="text-[15px] font-bold">{name}</h4>
        <StatusBadge status={shownStatus(t, d)} />
      </div>
      <p className={`text-[15px] font-semibold ${shown ? "" : "text-muted"}`}>{shown || "값이 없습니다"}</p>
      <p className="text-small leading-[1.6] text-muted">
        {t.quote ? (
          <>
            <span className="font-bold text-accent">{clauseLabel(t.source_clause_id)}</span> · {t.quote}
          </>
        ) : (
          "연결된 근거 조항이 없습니다."
        )}
      </p>
      {editing && (
        <div className="mt-1 flex flex-col gap-3 border-t border-line-soft pt-3">
          {isSelect ? (
            <ChoiceSelect termKey={t.key} label={`${name} 값`} value={d.text} onChange={(text) => onChange({ text })} />
          ) : (
            <Field label={`${name} 값`}>
              <input type="text" className={fieldClass} value={d.text} onChange={(e) => onChange({ text: e.target.value })} />
            </Field>
          )}
          <ConfirmToggle
            checked={d.confirmed}
            locked={lock}
            label={lock ? (isSelect ? "값을 고르면 확인할 수 있어요" : "값을 넣어야 확인할 수 있어요") : d.confirmed ? "확인했습니다" : "계약서와 이 값을 확인했습니다"}
            onChange={(confirmed) => onChange({ confirmed })}
          />
        </div>
      )}
      <button
        type="button"
        aria-expanded={editing}
        aria-label={`${name} ${editing ? "수정 접기" : "수정"}`}
        onClick={onToggleEdit}
        className="mt-1 inline-flex min-h-11 items-center self-start rounded-btn border border-field px-4 text-[13px] font-[650] hover:bg-surface"
      >
        {editing ? "접기" : "수정"}
      </button>
    </article>
  );
}

// ---------------------------------------------------------------- 화면

function TermsInner() {
  const id = useSearchParams().get("id") ?? "";
  // 상태가 바뀌면 탭 바(흐림)와 사이드바(상태)를 새로고침 없이 맞춘다
  const { reload: reloadContract } = useContract();
  const { reloadContracts } = useContracts();
  const [data, setData] = useState<TermsResponse | null>(null);
  const [drafts, setDrafts] = useState<Record<string, Draft>>({});
  const [message, setMessage] = useState("");
  const [reading, setReading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [editing, setEditing] = useState<Record<string, boolean>>({});
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
  }, [id, data]);

  function clauseLabel(clauseId: string | null | undefined) {
    if (!clauseId) return "연결된 조항 없음";
    if (clausesContractId !== id) return "조항 정보 불러오는 중…";
    const clause = clauses.find((item) => item.id === clauseId);
    if (!clause) {
      return clauseError || "조항 정보를 확인할 수 없습니다.";
    }

    const no = clause.no?.trim() || "번호 없는 조항";
    const title = clause.title?.trim();

    return title ? `${no} (${title})` : no;
  }
  const load = useCallback((res: TermsResponse) => {
    setData(res);
    setDrafts(Object.fromEntries(res.terms.map((t) => [t.key, toDraft(t)])));
  }, []);

  useEffect(() => {
    if (!id) return;
    let stop = false;
    // 계약서를 아직 읽는 중이면 조건이 비어 있고 저장도 막혀 있으므로(409), 끝날 때까지 기다렸다가 불러온다.
    (async () => {
      try {
        let waited = false;
        for (let i = 0; i < 90; i++) {
          const c = await api<ContractOut>(`/contracts/${id}`);
          if (stop) return;
          if (c.status === "처리 실패") {
            setReading(false);
            reloadContract();
            void reloadContracts().catch(() => {});
            return setMessage("계약서를 읽지 못했습니다. 첫 화면에서 다시 올려 주세요.");
          }
          if (c.status !== "처리중") break;
          waited = true;
          setReading(true);
          await new Promise((r) => setTimeout(r, 2000));
        }
        const res = await api<TermsResponse>(`/contracts/${id}/terms`);
        if (!stop) {
          setReading(false);
          setMessage("");
          load(res);
          if (waited) {
            // 읽는 중이던 계약서가 끝났으니 상태를 맞춘다
            reloadContract();
            void reloadContracts().catch(() => {});
          }
        }
      } catch (e) {
        if (!stop) {
          setReading(false);
          setMessage(errorText(e));
        }
      }
    })();
    return () => {
      stop = true;
    };
  }, [id, load, reloadContract, reloadContracts]);

  const set = (key: string, patch: Partial<Draft>) => setDrafts((prev) => ({ ...prev, [key]: { ...prev[key], ...patch } }));

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
      if (res.all_confirmed) {
        reloadContract();
        void reloadContracts().catch(() => {});
      }
      setMessage(res.all_confirmed ? "저장했습니다. 이제 정산서를 입력할 수 있습니다." : "저장했습니다.");
    } catch (e) {
      setMessage(errorText(e));
    } finally {
      setSaving(false);
    }
  }

  if (!id)
    return (
      <InfoPanel title="계약서를 먼저 선택해 주세요.">
        <Link className={buttonClass("primary")} href="/">
          계약서 올리러 가기
        </Link>
      </InfoPanel>
    );
  if (!data) {
    if (reading)
      return (
        <ProcessingState hint="보통 20초 안팎, 길면 1~2분 걸립니다. 끝나면 조건이 자동으로 나타납니다.">계약서를 읽는 중입니다.</ProcessingState>
      );
    if (message)
      return (
        <InfoPanel role="status" title={message}>
          {message.startsWith("계약서를 읽지 못했습니다") && (
            <Link className={buttonClass("secondary")} href="/">
              첫 화면으로
            </Link>
          )}
        </InfoPanel>
      );
    return <ProcessingState>불러오는 중…</ProcessingState>;
  }

  const byKey = Object.fromEntries(data.terms.map((t) => [t.key, t]));
  const required = REQUIRED.map((k) => byKey[k]).filter(Boolean);
  const optional = OPTIONAL.map((k) => byKey[k]).filter(Boolean);
  // 필수 조건 중 확인 표시를 한 개수 (개수 세기일 뿐 금액 계산이 아님)
  const done = required.filter((t) => drafts[t.key]?.confirmed && !blocked(t, drafts[t.key])).length;
  const total = required.length;
  const ready = data.all_confirmed;

  return (
    <>
      <Card className="flex flex-wrap items-center gap-5 !p-4 md:!px-7 md:!py-6">
        <div className="flex min-w-0 flex-[1_1_360px] flex-col gap-1.5">
          <h2 className="hidden text-title font-[750] md:block">조건 확인</h2>
          <p className="text-sm leading-[1.6] text-[#3a3f52] md:text-[15px]">
            계약서에서 찾은 정산 조건입니다. 원문과 비교해 값을 확인해 주세요. <b>확인한 조건만 계산에 씁니다.</b>
          </p>
        </div>
        <div className="flex min-w-0 flex-[0_1_260px] flex-col gap-2 max-md:basis-full">
          <p className="num text-[13px] font-[650] md:text-sm">
            필수 조건 {total}개 중 {done}개 확인
          </p>
          <div aria-hidden className="h-1.5 overflow-hidden rounded-[3px] bg-line-soft md:h-2">
            <div className="h-full rounded-[3px] bg-accent" style={{ width: `${total ? (done * 100) / total : 0}%` }} />
          </div>
        </div>
      </Card>

      <h3 className="mx-1 mt-1.5 text-base font-[750]">
        계산에 필요한 조건 <span className="text-small font-medium text-muted">필수</span>
      </h3>
      {required.map((t) => (
        <RequiredCard key={t.key} t={t} d={drafts[t.key]} onChange={(patch) => set(t.key, patch)} clauseLabel={clauseLabel} />
      ))}

      {optional.length > 0 && (
        <>
          <h3 className="mx-1 mt-1.5 text-base font-[750]">
            참고 조건 <span className="text-small font-medium text-muted">선택 · 계산에는 쓰지 않음</span>
          </h3>
          <div className="grid items-start gap-3 md:grid-cols-2">
            {optional.map((t) => (
              <OptionalCard
                key={t.key}
                t={t}
                d={drafts[t.key]}
                editing={!!editing[t.key]}
                onToggleEdit={() => setEditing((prev) => ({ ...prev, [t.key]: !prev[t.key] }))}
                onChange={(patch) => set(t.key, patch)}
                clauseLabel={clauseLabel}
              />
            ))}
          </div>
        </>
      )}

      <div className="sticky bottom-0 -mx-4 mt-1 flex flex-col gap-2 border-t border-line bg-surface px-4 py-3 md:-mx-6 md:px-6 md:py-3.5">
        {message && (
          <p role="status" className="text-sm font-medium text-ink-2">
            {message}
          </p>
        )}
        {/* 767px 이하에서는 설명 문장을 숨겨 한 줄(필수 n/5 · 저장 · 정산서 입력으로)로 줄인다 */}
        <div className="flex items-center gap-x-2 md:flex-wrap md:gap-x-4 md:gap-y-2">
          <span className="num whitespace-nowrap text-[13px] font-[650] text-ink-2 md:text-sm">
            필수 {done}/{total} 확인
          </span>
          <span className="hidden text-small text-muted md:inline">{ready ? "모든 필수 조건을 확인했어요." : "필수 조건을 모두 확인하고 저장하면 정산서 입력이 열립니다."}</span>
          <span className="flex-1" />
          <button type="button" disabled={saving} onClick={save} className={`${buttonClass("secondary")} whitespace-nowrap md:min-w-24 max-md:flex-1 max-md:!px-3`}>
            {saving ? "저장 중…" : "저장"}
          </button>
          {ready ? (
            <Link href={`/statements?id=${id}`} className={`${buttonClass("primary")} whitespace-nowrap max-md:flex-[1.6] max-md:!px-3`}>
              정산서 입력으로 →
            </Link>
          ) : (
            <span aria-disabled="true" className={`${buttonClass("primary")} pointer-events-none whitespace-nowrap !bg-locked max-md:flex-[1.6] max-md:!px-3`}>
              정산서 입력으로 →
            </span>
          )}
        </div>
      </div>
    </>
  );
}

export default function TermsPage() {
  return (
    <Suspense>
      <TermsInner />
    </Suspense>
  );
}
