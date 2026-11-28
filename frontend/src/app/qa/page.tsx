"use client";

import { ArrowRight } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState, type FormEvent } from "react";
import { InfoPanel } from "../../components/InfoPanel";
import { Spinner } from "../../components/Spinner";
import { api, errorText, type QAResult } from "../../lib/api";
import { buttonClass } from "../../lib/ui";

const MAX_QUESTION = 500; // 백엔드 MAX_QUESTION과 같게
const EXAMPLES = [
  "선급금(MG)은 얼마이고 어떻게 회수하나요?",
  "정산금은 언제 받나요?",
  "계약을 해지하려면 어떻게 해야 하나요?",
  "2차적저작물 작성권은 누구에게 있나요?",
];

type Citation = QAResult["citations"][number];

// "제7조 (정산 및 지급)" 모양의 조항 이름
function clauseName(c: Citation) {
  const no = c.clause_no?.trim();
  const title = c.clause_title?.trim();
  if (no && title) return `${no} (${title})`;
  return no || title || c.clause_id;
}

function sourceLabel(c: Citation) {
  if (c.source === "law") {
    const when = c.effective_date ? ` (${c.effective_date} 시행)` : "";
    return `법령 · ${c.law_name ?? ""} ${clauseName(c)}${when}`;
  }
  // 표준계약서는 법령이 아니라 문체부 고시라서 법령과 다른 이름으로 보인다
  const where = c.source === "standard" ? "표준계약서 (문체부 고시, 법령 아님)" : "내 계약서";
  return `${where} · ${clauseName(c)}`;
}

// 출처 종류는 색이 아니라 모양으로만 구분한다 (색으로 신뢰도처럼 보이게 하지 않음):
// 내 계약서 = 흰 바탕 + 실선 테두리 라벨, 표준계약서 = 회색 채움 라벨, 법령 = 점선 테두리 라벨 + 흰 바탕 블록
const LABEL_SHAPE: Record<Citation["source"], string> = {
  contract: "border border-solid border-line bg-card",
  standard: "bg-line-soft",
  law: "border border-dashed border-dash",
};

function QAInner() {
  const id = useSearchParams().get("id") ?? "";
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [history, setHistory] = useState<QAResult[]>([]); // 이 화면에서 한 질문만 (새로 고치면 사라짐)
  const [copied, setCopied] = useState(-1);
  const last = useRef<HTMLElement>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  useEffect(() => () => clearTimeout(timer.current), []);

  // 새 답이 오면 그 위치로 스크롤 (움직임을 줄인 설정이면 그대로 이동)
  useEffect(() => {
    if (history.length === 0) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    last.current?.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
  }, [history.length]);

  async function ask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const q = question.trim();
    if (!q || busy) return;
    setBusy(true);
    setError("");
    try {
      const result = await api<QAResult>(`/contracts/${id}/qa`, {
        method: "POST",
        body: JSON.stringify({ question: q }),
      });
      setHistory((h) => [...h, result]);
      setQuestion("");
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }

  async function copyAnswer(i: number, text: string) {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(i);
    } catch {
      setCopied(-1);
    }
    clearTimeout(timer.current);
    timer.current = setTimeout(() => setCopied(-1), 3000);
  }

  if (!id)
    return (
      <InfoPanel title="계약서를 먼저 선택해 주세요.">
        <Link className={buttonClass("primary")} href="/">
          계약서 올리러 가기
        </Link>
      </InfoPanel>
    );

  return (
    <section className="flex min-h-[560px] flex-col gap-[22px] rounded-[12px] bg-card px-4 pb-5 pt-6 shadow-card md:min-h-[640px] md:px-7">
      <div className="mx-auto flex w-full max-w-[760px] flex-1 flex-col gap-7">
        {history.length === 0 && (
          <p className="my-auto py-10 text-center text-sm leading-relaxed text-muted">
            계약서에 궁금한 점을 아래에 적거나 예시 질문을 눌러 보세요.
            <br />
            계약서에서 관련 조항을 찾아 원문과 함께 보여 드립니다.
          </p>
        )}
        {history.map((r, i) => (
          <article
            key={i}
            ref={i === history.length - 1 ? last : undefined}
            className="flex scroll-mt-4 flex-col gap-3 border-line-soft [&:not(:first-child)]:border-t [&:not(:first-child)]:pt-7"
          >
            <div className="flex items-center gap-2.5">
              <span aria-hidden className="grid size-7 shrink-0 place-items-center rounded-field bg-accent-soft text-fine font-extrabold text-accent">
                나
              </span>
              <p className="min-w-0 break-words text-sm text-ink-2">{r.question}</p>
            </div>
            <span className="text-fine font-extrabold tracking-[0.16em] text-accent">OPENBOOK</span>
            <p className="text-base font-semibold leading-[1.7]">{r.answer}</p>

            {r.citations.length > 0 && (
              <div className="flex flex-col gap-2">
                <h3 className="text-small font-bold text-muted">근거 원문</h3>
                {r.citations.map((c, j) => (
                  <blockquote
                    key={j}
                    className={`flex flex-col gap-1.5 rounded-field px-4 py-3.5 ${c.source === "law" ? "border border-line bg-card" : "bg-quote"}`}
                  >
                    <span className={`self-start rounded-tag px-2.5 py-[3px] text-fine font-bold ${LABEL_SHAPE[c.source]}`}>{sourceLabel(c)}</span>
                    <p className={`whitespace-pre-wrap text-sm leading-[1.7] ${c.source === "law" ? "text-ink-2" : ""}`}>{c.quote}</p>
                    {c.source === "law" && c.source_url && (
                      <a className="text-small font-[650] text-accent underline" href={c.source_url} target="_blank" rel="noreferrer">
                        국가법령정보센터에서 현행 원문 보기
                      </a>
                    )}
                  </blockquote>
                ))}
                {r.basis && <p className="text-fine text-muted">표준계약서 기준 · {r.basis}</p>}
                {r.citations.some((c) => c.source === "law") && (
                  <p className="text-fine text-muted">법령 조문은 적힌 내용만 옮긴 것이고, 이 계약에 어떻게 적용되는지는 판단하지 않습니다.</p>
                )}
              </div>
            )}
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={() => copyAnswer(i, r.answer)}
                className="min-h-11 rounded-btn border border-line px-3 text-fine font-[650] text-ink-2 hover:bg-surface"
              >
                {copied === i ? "복사했습니다" : "답 복사"}
              </button>
              <span className="text-fine text-muted">{r.notice}</span>
            </div>
          </article>
        ))}
      </div>

      <div className="mx-auto flex w-full max-w-[760px] flex-col gap-2.5">
        {busy && (
          <p role="status" className="flex items-center gap-2 text-sm text-ink-2">
            <Spinner />
            계약서에서 찾는 중입니다. 10~30초 걸릴 수 있습니다.
          </p>
        )}
        {error && (
          <p role="alert" className="text-sm text-error">
            {error}
          </p>
        )}
        <div className="flex flex-wrap gap-2">
          {EXAMPLES.map((q) => (
            <button
              key={q}
              type="button"
              onClick={() => setQuestion(q)}
              className="min-h-11 rounded-field border border-line bg-card px-3.5 text-[13px] text-ink-2 hover:bg-surface"
            >
              {q}
            </button>
          ))}
        </div>
        <form
          onSubmit={ask}
          className="flex items-center gap-2.5 rounded-btn border border-line bg-card py-2 pl-[18px] pr-2 shadow-[0_8px_24px_rgb(40_56_110/0.10)] focus-within:ring-2 focus-within:ring-accent"
        >
          <label htmlFor="qa-question" className="sr-only">
            질문
          </label>
          <input
            id="qa-question"
            className="h-10 min-w-0 flex-1 bg-transparent text-[15px] outline-none"
            value={question}
            maxLength={MAX_QUESTION}
            placeholder="계약서에 궁금한 점을 물어보세요"
            onChange={(e) => setQuestion(e.target.value)}
          />
          <button
            type="submit"
            aria-label="질문 보내기"
            disabled={busy || !question.trim()}
            className="grid size-11 shrink-0 place-items-center rounded-btn bg-accent text-white disabled:cursor-not-allowed disabled:bg-locked"
          >
            <ArrowRight size={18} strokeWidth={2.2} aria-hidden />
          </button>
        </form>
        <p className="text-center text-fine text-muted">계약서에서 관련 조항을 찾아 원문과 함께 보여 드려요. 금액 계산은 대조 결과에서 하세요.</p>
      </div>
    </section>
  );
}

export default function QAPage() {
  return (
    <Suspense>
      <QAInner />
    </Suspense>
  );
}
