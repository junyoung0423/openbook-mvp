"use client";

import { useState, type FormEvent } from "react";
import sampleA from "../../../docs/mock/process_result_ok_sample_a.json";
import sampleB from "../../../docs/mock/process_result_ok_sample_b.json";
import extractionError from "../../../docs/mock/process_result_llm_error.json";
import noClauses from "../../../docs/mock/process_result_no_clauses.json";

const samples = {
  "정상 · 경고 있음": sampleA,
  "일부 조건을 찾지 못함": sampleB,
  "조건 추출 실패": extractionError,
  "조항 분할 실패": noClauses,
};

type Scenario = keyof typeof samples;

const termLabels: Record<string, string> = {
  mg_amount: "MG 금액",
  mg_pay_date: "MG 지급 시점",
  mg_recoup: "MG 회수 방식",
  mg_carryover: "미회수 MG 처리",
  rs_rate: "RS 배분율",
  revenue_base: "정산 기준 매출",
  deductions: "공제 항목",
  settlement_cycle: "정산 주기",
  payment_day: "정산금 지급 시점",
};

const field = "block w-full rounded-lg border border-stone-300 bg-white p-2";
const button =
  "rounded-lg bg-teal-900 px-4 py-2 text-white disabled:cursor-not-allowed disabled:opacity-50";
const optionLabels: Record<string, Record<string, string>> = {
  mg_recoup: {
    from_rs: "RS에서 차감",
    separate: "별도 처리",
    unknown: "확인 필요",
  },
  mg_carryover: {
    carry_over: "이월",
    refund: "반환",
    forgiven: "반환 요구 없음",
    unknown: "확인 필요",
  },
  revenue_base: {
    gross: "총매출",
    net: "순매출",
    other: "기타",
  },
  settlement_cycle: {
    monthly: "월별",
    quarterly: "분기별",
    semiannual: "반기별",
    other: "기타",
  },
};
  function formatTermValue(key: string, value: string) {
  if (key === "mg_amount" && /^\d+$/.test(value)) {
    return `${value.replace(/\B(?=(\d{3})+(?!\d))/g, ",")}원`;
  }

  if (key === "rs_rate" && /^\d+(\.\d+)?$/.test(value)) {
    const [whole, fraction = ""] = value.split(".");
    const digits = (whole + fraction.padEnd(2, "0").slice(0, 2))
      .replace(/^0+(?=\d)/, "");
    const remaining = fraction.slice(2).replace(/0+$/, "");
    return `${digits}${remaining ? `.${remaining}` : ""}%`;
  }

  return optionLabels[key]?.[value] ?? value;
}
export default function Home() {
  const [scenario, setScenario] = useState<Scenario>("정상 · 경고 있음");
  const [mode, setMode] = useState<"file" | "text">("file");
  const [file, setFile] = useState<File | null>(null);
  const [text, setText] = useState("");
  const [consent, setConsent] = useState(false);
  const [screen, setScreen] = useState<"upload" | "processing" | "review">("upload");

  const result = samples[scenario];
  const validFile =
    Boolean(file?.size) && /\.(pdf|docx|hwp|jpe?g|png|webp|tiff?|bmp|heic)$/i.test(file?.name ?? "");
  const canSubmit = consent && (mode === "file" ? validFile : Boolean(text.trim()));

  function processSample() {
    setScreen("processing");
    window.setTimeout(() => setScreen("review"), 700);
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (canSubmit) processSample();
  }

  function returnToUpload() {
    setFile(null);
    if (!result.clauses.length) setMode("text");
    setScreen("upload");
  }

  return (
    <main className="min-h-screen bg-stone-100 px-5 py-10 text-stone-900">
      <div className="mx-auto max-w-2xl space-y-5">
        <header className="font-bold text-teal-900">오픈북</header>

        {screen === "upload" && (
          <form onSubmit={submit} className="space-y-5 rounded-2xl bg-white p-6">
            <h1 className="text-2xl font-bold">계약서 업로드</h1>

            <fieldset className="flex flex-wrap gap-4">
              <legend className="mb-2 font-medium">입력 방식</legend>
              <label>
                <input type="radio" name="mode" checked={mode === "file"} onChange={() => setMode("file")} />{" "}
                파일 선택
              </label>
              <label>
                <input type="radio" name="mode" checked={mode === "text"} onChange={() => setMode("text")} />{" "}
                본문 붙여넣기
              </label>
            </fieldset>

            <div hidden={mode !== "file"}>
              <label htmlFor="contract-file" className="block font-medium">계약서 파일</label>
              <p className="mb-2 text-sm">PDF, DOCX, HWP, 사진·스캔 이미지</p>
              <input
                id="contract-file"
                type="file"
                className={field}
                accept=".pdf,.docx,.hwp,.jpg,.jpeg,.png,.webp,.tif,.tiff,.bmp,.heic"
                onChange={(event) => setFile(event.target.files?.[0] ?? null)}
              />
              {file && !validFile && (
                <p role="alert" className="mt-2 text-sm">지원하는 형식의 비어 있지 않은 파일을 선택해 주세요.</p>
              )}
            </div>

            {mode === "text" && (
              <label className="block">
                계약서 본문
                <textarea className={field} rows={6} value={text} onChange={(event) => setText(event.target.value)} />
              </label>
            )}

            <div className="space-y-3 rounded-lg bg-stone-100 p-4 text-sm">
              <p id="privacy-notice">
                계약서에는 실명·연락처·계좌 등이 있을 수 있습니다. 실제 분석에서는 계약서 내용이
                Upstage Document Parse(문서 파싱)와 Solar Pro 4(분석)에 전송됩니다.
                이 목 데이터 화면에서는 입력한 내용이 전송되지 않습니다.
              </p>
              <label className="flex items-start gap-2">
                <input
                  className="mt-1"
                  type="checkbox"
                  aria-describedby="privacy-notice"
                  checked={consent}
                  onChange={(event) => setConsent(event.target.checked)}
                />
                개인정보 안내를 확인했으며 외부 서비스 전송에 동의합니다.
              </label>
            </div>

            <label className="block">
              목 데이터 시나리오
              <select className={field} value={scenario} onChange={(event) => setScenario(event.target.value as Scenario)}>
                {Object.keys(samples).map((name) => <option key={name}>{name}</option>)}
              </select>
            </label>

            <button className={button} disabled={!canSubmit} type="submit">업로드</button>
          </form>
        )}

        {screen === "processing" && (
          <p role="status" className="rounded-2xl bg-white p-6">계약서 처리 중…</p>
        )}

        {screen === "review" && (
          <section className="space-y-4 rounded-2xl bg-white p-6">
            <h1 className="text-2xl font-bold">계약서 조항 확인</h1>

            {result.warnings.map((warning) => (
              <p key={warning} className="rounded-lg border border-stone-300 bg-stone-100 p-3">{warning}</p>
            ))}

            {result.clauses.length ? (
              <details open={!result.terms}>
                <summary className="cursor-pointer font-medium">전체 조항 원문 ({result.clauses.length}개)</summary>
                {result.clauses.map((clause) => (
                  <article key={clause.id} className="mt-3 border-t border-stone-200 pt-3">
                    <h2 className="font-medium">{[clause.no, clause.title].filter(Boolean).join(" ")}</h2>
                    <p className="whitespace-pre-wrap">{clause.text}</p>
                  </article>
                ))}
              </details>
            ) : (
              <p>조항을 나누지 못했습니다. 조항별로 본문을 나누어 다시 붙여넣어 주세요.</p>
            )}

            {result.error && (
              <div className="space-y-2">
                <p>조건 추출에 실패했습니다.</p>
                <button className={button} type="button" onClick={processSample}>다시 시도</button>
              </div>
            )}

            {result.terms?.terms.map((term) => {
              const clause = result.clauses.find((item) => item.id === term.source_clause_id);

              return (
                <article key={term.key} className="space-y-2 rounded-lg border border-stone-200 p-3">
                  <h2 className="font-medium">{termLabels[term.key] ?? term.key}</h2>
                  {term.status === "not_found" ? (
                    <>
                      <p>찾지 못함</p>
                      <label className="block">
                        직접 입력
                        <input className={field} aria-label={`${termLabels[term.key]} 직접 입력`} />
                      </label>
                    </>
                  ) : (
                    <>
                      <p>{term.status === "user_input" ? "직접 입력" : "추출됨"}</p>
                      {typeof term.value === "string" && (
                        <p>{formatTermValue(term.key, term.value)}</p>
                      )}
                      {term.key === "deductions" && Array.isArray(term.value) && (
                        <ul className="list-inside list-disc">
                          {term.value.map((item, index) => (
                            <li key={index}>
                              {item.name}
                              {typeof item.rate === "string" && ` · ${formatTermValue("rs_rate", item.rate)}`}
                              {typeof item.amount === "string" && ` · ${formatTermValue("mg_amount", item.amount)}`}
                            </li>
                          ))}
                        </ul>
                      )}
                    </>
                  )}
                  {term.quote && (
                    <blockquote className="whitespace-pre-wrap border-l-2 border-stone-300 pl-3">
                      <span className="block font-medium">근거 조항 {clause?.no ?? term.source_clause_id}</span>
                      {term.quote}
                    </blockquote>
                  )}
                </article>
              );
            })}

            <button type="button" className="rounded-lg border border-stone-300 px-4 py-2" onClick={returnToUpload}>
              {result.clauses.length ? "입력 화면으로 돌아가기" : "본문 붙여넣기"}
            </button>
          </section>
        )}
      </div>
    </main>
  );
}