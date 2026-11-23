"use client";

import { useState, type FormEvent } from "react";

export default function StatementsPage() {
  const [periodStart, setPeriodStart] = useState("");
  const [periodEnd, setPeriodEnd] = useState("");
  const [gross, setGross] = useState("");
  const [reportedPayout, setReportedPayout] = useState("");
  const [deductions, setDeductions] = useState<
    { name: string; amount: string }[]
  >([]);
  const [error, setError] = useState("");
  const [preview, setPreview] = useState("");

  const field =
    "mt-2 w-full rounded-lg border border-stone-300 bg-white p-2";

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setPreview("");

    if (!periodStart || !periodEnd) {
      setError("정산 기간을 입력해 주세요.");
      return;
    }

    if (periodEnd < periodStart) {
      setError("정산 기간의 끝이 시작보다 앞입니다.");
      return;
    }

    const money = /^\d+(\.\d+)?$/;

    if (!money.test(gross) || !money.test(reportedPayout)) {
      setError("총매출과 지급액을 쉼표 없이 숫자로 입력해 주세요.");
      return;
    }

    if (
      deductions.some(
        (item) => !item.name.trim() || !money.test(item.amount)
      )
    ) {
      setError("공제 항목의 이름과 금액을 확인해 주세요.");
      return;
    }

    setPreview(
      JSON.stringify(
        {
          period_start: periodStart,
          period_end: periodEnd,
          gross,
          deductions,
          reported_payout: reportedPayout,
        },
        null,
        2
      )
    );
  }

  return (
    <main className="min-h-screen bg-stone-100 px-5 py-10 text-stone-900">
      <form
        onSubmit={submit}
        onChange={() => {
          setPreview("");
          setError("");
        }}
        className="mx-auto max-w-3xl space-y-5 rounded-2xl bg-white p-6"
      >
        <header className="font-bold text-teal-900">오픈북</header>
        <h1 className="text-2xl font-bold">정산서 입력</h1>
        <p>정산서에 적힌 값을 입력해 주세요.</p>

        <div className="grid gap-4 sm:grid-cols-2">
          <label>
            정산 시작일
            <input
              type="date"
              required
              className={field}
              value={periodStart}
              onChange={(event) => setPeriodStart(event.target.value)}
            />
          </label>

          <label>
            정산 종료일
            <input
              type="date"
              required
              className={field}
              value={periodEnd}
              onChange={(event) => setPeriodEnd(event.target.value)}
            />
          </label>
        </div>

        <label className="block">
          정산서 총매출 (원)
          <input
            type="text"
            inputMode="decimal"
            required
            className={field}
            value={gross}
            onChange={(event) => setGross(event.target.value)}
          />
        </label>

        <fieldset className="space-y-3">
          <legend className="mb-2 font-semibold">정산서 공제 항목</legend>
          <p className="text-sm text-stone-600">
            정산서에 공제 내역이 있으면 추가해 주세요.
          </p>

          {deductions.map((item, index) => (
            <div
              key={index}
              className="space-y-3 rounded-lg border border-stone-200 p-4"
            >
              <label className="block">
                항목 이름
                <input
                  required
                  className={field}
                  value={item.name}
                  onChange={(event) =>
                    setDeductions((previous) =>
                      previous.map((row, rowIndex) =>
                        rowIndex === index
                          ? { ...row, name: event.target.value }
                          : row
                      )
                    )
                  }
                />
              </label>

              <label className="block">
                공제 금액 (원)
                <input
                  type="text"
                  inputMode="decimal"
                  required
                  className={field}
                  value={item.amount}
                  onChange={(event) =>
                    setDeductions((previous) =>
                      previous.map((row, rowIndex) =>
                        rowIndex === index
                          ? { ...row, amount: event.target.value }
                          : row
                      )
                    )
                  }
                />
              </label>

              <button
                type="button"
                className="rounded-lg border border-stone-300 px-3 py-2"
                onClick={() => {
                  setDeductions((previous) =>
                    previous.filter((_, rowIndex) => rowIndex !== index)
                  );
                  setPreview("");
                }}
              >
                이 공제 항목 삭제
              </button>
            </div>
          ))}

          <button
            type="button"
            className="rounded-lg border border-stone-300 px-3 py-2"
            onClick={() => {
              setDeductions((previous) => [
                ...previous,
                { name: "", amount: "" },
              ]);
              setPreview("");
            }}
          >
            공제 항목 추가
          </button>
        </fieldset>

        <label className="block">
          정산서에 적힌 지급액 (원)
          <input
            type="text"
            inputMode="decimal"
            required
            className={field}
            value={reportedPayout}
            onChange={(event) => setReportedPayout(event.target.value)}
          />
        </label>

        {error && <p role="alert">{error}</p>}

        <button
          type="submit"
          className="rounded-lg bg-teal-900 px-4 py-2 text-white"
        >
          입력 내용 확인
        </button>

        {preview && (
          <details open>
            <summary>개발 확인용 요청 본문</summary>
            <pre className="mt-3 overflow-auto whitespace-pre-wrap text-sm">
              {preview}
            </pre>
          </details>
        )}
      </form>
    </main>
  );
}