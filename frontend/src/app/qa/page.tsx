"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState, type FormEvent } from "react";
import { api, errorText, field, primary, secondary, type QAResult } from "../../lib/api";

const MAX_QUESTION = 500; // 백엔드 MAX_QUESTION과 같게
const EXAMPLES = ["선급금(MG)은 얼마이고 어떻게 회수하나요?", "정산금은 언제 받나요?", "계약을 해지하려면 어떻게 해야 하나요?"];

function sourceLabel(c: QAResult["citations"][number]) {
  const where = c.source === "standard" ? "표준계약서" : "내 계약서";
  const name = [c.clause_no, c.clause_title].filter(Boolean).join(" ");
  return `${where} · ${name || c.clause_id}`;
}

function QAInner() {
  const id = useSearchParams().get("id") ?? "";
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [history, setHistory] = useState<QAResult[]>([]); // 이 화면에서 한 질문만 (새로 고치면 사라짐)

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
      setHistory((h) => [result, ...h]);
      setQuestion("");
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }

  if (!id) return <p className="rounded-2xl bg-white p-6">계약서를 먼저 선택해 주세요.</p>;

  return (
    <>
      <form onSubmit={ask} className="space-y-4 rounded-2xl bg-white p-6">
        <h1 className="text-2xl font-bold">계약서에 질문하기</h1>
        <p className="text-stone-600">
          계약서에서 관련 조항을 찾아 원문과 함께 보여 드립니다. 금액 계산은 정산 대조 화면에서 하세요.
        </p>
        <label className="block">
          질문
          <textarea
            className={field}
            rows={3}
            maxLength={MAX_QUESTION}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
          />
        </label>
        <div className="flex flex-wrap gap-2 text-sm">
          {EXAMPLES.map((q) => (
            <button key={q} type="button" className={secondary} onClick={() => setQuestion(q)}>
              {q}
            </button>
          ))}
        </div>
        <button className={primary} disabled={busy || !question.trim()} type="submit">
          {busy ? "찾는 중…" : "질문하기"}
        </button>
        {busy && <p role="status">계약서에서 찾는 중입니다. 10~30초 걸릴 수 있습니다.</p>}
        {error && <p role="alert">{error}</p>}
      </form>

      {history.map((r, i) => (
        <article key={history.length - i} className="space-y-4 rounded-2xl bg-white p-6">
          <p className="text-sm text-stone-600">질문</p>
          <p className="font-medium">{r.question}</p>
          <p className="text-sm text-stone-600">답</p>
          <p className="text-lg">{r.answer}</p>

          {r.citations.length > 0 && (
            <div className="space-y-3">
              <h2 className="font-semibold">근거 원문</h2>
              {r.citations.map((c, j) => (
                <blockquote key={j} className="rounded-xl bg-stone-100 p-4">
                  <p className="text-sm text-stone-600">{sourceLabel(c)}</p>
                  <p className="mt-1 whitespace-pre-wrap">{c.quote}</p>
                </blockquote>
              ))}
              {r.basis && <p className="text-sm text-stone-600">표준계약서 기준 · {r.basis}</p>}
            </div>
          )}
          <p className="text-sm text-stone-600">{r.notice}</p>
        </article>
      ))}

      <div className="flex flex-wrap gap-2">
        <Link className={secondary} href={`/terms?id=${id}`}>
          조건
        </Link>
        <Link className={secondary} href={`/results?id=${id}`}>
          대조 결과
        </Link>
      </div>
    </>
  );
}

export default function QAPage() {
  return (
    <main className="min-h-screen bg-stone-100 px-4 py-10 text-stone-900">
      <div className="mx-auto max-w-3xl space-y-6">
        <Link href="/" className="font-bold text-teal-900">
          오픈북
        </Link>
        <Suspense>
          <QAInner />
        </Suspense>
      </div>
    </main>
  );
}
