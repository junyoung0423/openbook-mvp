"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import type { Deduction, TermSet } from "../../types/terms.generated";
import sampleA from "../../../../docs/mock/api/terms_get_sample_a.json";
import sampleB from "../../../../docs/mock/api/terms_get_sample_b.json";
import extractionFailed from "../../../../docs/mock/api/terms_get_extraction_failed.json";
import schema from "../../../../docs/schemas/terms.schema.json";
import confirmedSample from "../../../../docs/mock/api/terms_put_confirm_sample_a.json";
import invalidSample from "../../../../docs/mock/api/terms_put_invalid.json";

const samples = {
    normal: sampleA,
    partial: sampleB,
    failed: extractionFailed,
};

type Scenario = keyof typeof samples;

type TermsResponse = TermSet & {
    missing_keys: string[];
    unconfirmed_required: string[];
    all_confirmed: boolean;
};

const labels: Record<string, string> = {
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

const statusLabels = {
    extracted: "추출됨",
    not_found: "찾지 못함",
    user_input: "직접 입력",
};
const choices: Record<string, readonly string[]> = {
    mg_recoup: schema.$defs.MgRecoup.enum,
    revenue_base: schema.$defs.RevenueBase.enum,
    settlement_cycle: schema.$defs.SettlementCycle.enum,
};

const choiceLabels: Record<string, string> = {
    from_rs: "RS에서 차감",
    separate: "별도 처리",
    unknown: "확인 필요",
    gross: "총매출",
    net: "순매출",
    other: "기타",
    monthly: "월별",
    quarterly: "분기별",
    semiannual: "반기별",
};
export default function TermsPage() {
    const router = useRouter();
    const [scenario, setScenario] = useState<Scenario>("normal");
    const [edits, setEdits] = useState<Record<string, string>>({});
    const [deductionEdits, setDeductionEdits] =
        useState<Deduction[] | null>(null);
    const [checkedValues, setCheckedValues] =
        useState<Record<string, string>>({});
    const [showErrors, setShowErrors] = useState(false);
    const [requestPreview, setRequestPreview] = useState("");
    const [saveMessage, setSaveMessage] = useState("");
    const [savedSnapshot, setSavedSnapshot] = useState<string | null>(null);
    const [saveMode, setSaveMode] = useState<"success" | "invalid">("success");

    const response = samples[scenario] as unknown as TermsResponse;

    const deductionTerm = response.terms.find(
        (term) => term.key === "deductions"
    );

    const deductions: Deduction[] =
        deductionEdits ??
        (Array.isArray(deductionTerm?.value)
            ? (deductionTerm.value as Deduction[])
            : []);

    function updateDeduction(index: number, changes: Partial<Deduction>) {
        setDeductionEdits(
            deductions.map((item, itemIndex) =>
                itemIndex === index ? { ...item, ...changes } : item
            )
        );
    }
    function confirmationValue(key: string, originalValue: unknown) {
        const value =
            key === "deductions"
                ? deductions
                : edits[key] ?? originalValue;

        return JSON.stringify([scenario, value]);
    }
    function currentValue(key: string, originalValue: unknown) {
        if (key === "deductions") {
            return deductionEdits ?? originalValue;
        }

        return edits[key] ?? originalValue;
    }

    function validationMessage(key: string, value: unknown): string {
        if (value == null || (typeof value === "string" && !value.trim())) {
            return "값을 입력해 주세요.";
        }

        if (key === "mg_amount") {
            const pattern = schema.$defs.RsTier.properties.from_amount.pattern;
            if (typeof value !== "string" || !new RegExp(pattern).test(value)) {
                return "금액을 쉼표 없이 숫자로 입력해 주세요.";
            }
        }

        if (key === "rs_rate") {
            const pattern = schema.$defs.RsTier.properties.rate.pattern;

            if (Array.isArray(value)) {
                return "구간별 RS는 MVP 계산을 지원하지 않습니다.";
            }

            if (typeof value !== "string" || !new RegExp(pattern).test(value)) {
                return "비율을 0~1로 입력해 주세요. 예를 들어 60%는 0.6입니다.";
            }
        }

        if (choices[key]) {
            if (typeof value !== "string" || !choices[key].includes(value)) {
                return "선택값을 확인해 주세요.";
            }
        }

        if (key === "deductions") {
            if (!Array.isArray(value)) return "공제 항목을 직접 입력해 주세요.";

            const moneyPattern = new RegExp(
                schema.$defs.RsTier.properties.from_amount.pattern
            );
            const ratePattern = new RegExp(
                schema.$defs.RsTier.properties.rate.pattern
            );

            for (const item of value as Deduction[]) {
                if (!item.name.trim()) return "공제 항목 이름을 입력해 주세요.";

                const hasRate = item.rate != null;
                const hasAmount = item.amount != null;

                if (hasRate === hasAmount) {
                    return "각 공제 항목에는 비율이나 금액 중 하나를 입력해 주세요.";
                }

                if (hasRate && !ratePattern.test(item.rate!)) {
                    return "공제 비율을 0~1로 입력해 주세요.";
                }

                if (hasAmount && !moneyPattern.test(item.amount!)) {
                    return "공제 금액을 쉼표 없이 숫자로 입력해 주세요.";
                }
            }
        }

        return "";
    }

    const requiredKeys = response.unconfirmed_required;

    function prepareConfirmation() {
        setShowErrors(true);
        setRequestPreview("");

        if (response.missing_keys.length > 0) return;

        const requiredValid = requiredKeys.every((key) => {
            const term = response.terms.find((item) => item.key === key);

            return (
                term !== undefined &&
                !validationMessage(key, currentValue(key, term.value)) &&
                checkedValues[key] === confirmationValue(key, term.value)
            );
        });

        const editedValid = response.terms.every((term) => {
            const edited =
                edits[term.key] !== undefined ||
                (term.key === "deductions" && deductionEdits !== null);

            return (
                !edited ||
                !validationMessage(
                    term.key,
                    currentValue(term.key, term.value)
                )
            );
        });

        if (!requiredValid || !editedValid) return;

        const terms = response.terms
            .filter(
                (term) =>
                    requiredKeys.includes(term.key) ||
                    edits[term.key] !== undefined ||
                    (term.key === "deductions" && deductionEdits !== null)
            )
            .map((term) => ({
                key: term.key,
                value: currentValue(term.key, term.value),
                confirmed: requiredKeys.includes(term.key),
            }));

        setRequestPreview(JSON.stringify({ terms }, null, 2));
    }
    const formSnapshot = JSON.stringify({
        scenario,
        edits,
        deductionEdits,
        checkedValues,
    });

    const canContinue =
        savedSnapshot === formSnapshot && confirmedSample.all_confirmed;

    function saveMockResponse() {
        setSaveMessage("");
        setSavedSnapshot(null);

        if (!requestPreview) {
            setSaveMessage("먼저 현재 값으로 확정 요청을 확인해 주세요.");
            return;
        }

        const request = JSON.parse(requestPreview) as {
            terms: {
                key: string;
                value: unknown;
                confirmed: boolean;
            }[];
        };

        const matchesCurrent = request.terms.every((submitted) => {
            const term = response.terms.find(
                (item) => item.key === submitted.key
            );

            return (
                term !== undefined &&
                JSON.stringify(submitted.value) ===
                JSON.stringify(currentValue(term.key, term.value)) &&
                (!submitted.confirmed ||
                    checkedValues[term.key] ===
                    confirmationValue(term.key, term.value))
            );
        });

        if (!matchesCurrent) {
            setSaveMessage("입력값이 바뀌었습니다. 확정 요청을 다시 확인해 주세요.");
            return;
        }

        if (saveMode === "invalid") {
            setSaveMessage(invalidSample.detail.message);
            return;
        }

        const matchesFixture =
            response.contract_id === confirmedSample.contract_id &&
            request.terms.every((submitted) => {
                const saved = confirmedSample.terms.find(
                    (item) => item.key === submitted.key
                );

                return (
                    saved !== undefined &&
                    JSON.stringify(submitted.value) === JSON.stringify(saved.value) &&
                    submitted.confirmed === saved.confirmed
                );
            }) &&
            response.unconfirmed_required.every((key) =>
                request.terms.some(
                    (item) => item.key === key && item.confirmed
                )
            );

        if (!matchesFixture) {
            setSaveMessage(
                "이 요청에 해당하는 저장 성공 목 데이터가 없습니다. 샘플 A의 원래 값으로 성공 화면을 확인해 주세요."
            );
            return;
        }

        setSavedSnapshot(formSnapshot);
        setSaveMessage("목 데이터의 저장 성공 응답을 확인했습니다.");
    }

    return (
        <main className="min-h-screen bg-stone-100 px-5 py-10 text-stone-900">
            <div className="mx-auto max-w-3xl space-y-5">
                <header className="font-bold text-teal-900">오픈북</header>

                <section className="space-y-4 rounded-2xl bg-white p-6">
                    <h1 className="text-2xl font-bold">조건 확인·수정</h1>

                    <label className="block">
                        목 데이터 시나리오
                        <select
                            className="mt-2 w-full rounded-lg border border-stone-300 p-2"
                            value={scenario}
                            onChange={(event) => {
                                setScenario(event.target.value as Scenario);
                                setEdits({});
                                setDeductionEdits(null);
                                setCheckedValues({});
                            }}
                        >
                            <option value="normal">샘플 A · 정상 추출</option>
                            <option value="partial">샘플 B · 일부 찾지 못함</option>
                            <option value="failed">조건 추출 실패</option>
                        </select>
                    </label>

                    {scenario === "failed" && (
                        <p role="status" className="rounded-lg bg-stone-100 p-3">
                            조건을 추출하지 못했습니다. 계약서 원문을 확인하고
                            조건을 직접 입력해 주세요.
                        </p>
                    )}

                    {response.missing_keys.length > 0 && (
                        <p role="status">
                            응답에 없는 조건 ·{" "}
                            {response.missing_keys
                                .map((key) => labels[key] ?? key)
                                .join(", ")}
                        </p>
                    )}

                    <p>
                        확인이 필요한 필수 조건 ·{" "}
                        {response.unconfirmed_required
                            .map((key) => labels[key] ?? key)
                            .join(", ") || "없음"}
                    </p>
                </section>

                {response.terms.map((term) => (
                    <article
                        key={term.key}
                        className="space-y-3 rounded-2xl bg-white p-6"
                    >
                        <div className="flex flex-wrap items-center justify-between gap-2">
                            <h2 className="text-lg font-semibold">
                                {labels[term.key] ?? term.key}
                            </h2>
                            <span className="rounded border border-stone-300 px-2 py-1 text-sm">
                                {edits[term.key] !== undefined ||
                                    (term.key === "deductions" && deductionEdits !== null)
                                    ? "직접 입력"
                                    : statusLabels[term.status]}
                            </span>
                        </div>

                        {response.unconfirmed_required.includes(term.key) && (
                            <p className="font-medium">확인해 주세요</p>
                        )}

                        {term.status === "not_found" && (
                            <p className="text-sm text-stone-600">
                                계약서에서 이 조건을 찾지 못했습니다.
                                표준·일반 조건과 같다는 뜻이 아닙니다.
                            </p>
                        )}
                        {term.key !== "deductions" && term.key !== "mg_carryover" && (
                            <label className="block">
                                값
                                {choices[term.key] ? (
                                    <select
                                        className="mt-2 w-full rounded-lg border border-stone-300 p-2"
                                        value={
                                            edits[term.key] ??
                                            (typeof term.value === "string" ? term.value : "")
                                        }
                                        onChange={(event) =>
                                            setEdits((previous) => ({
                                                ...previous,
                                                [term.key]: event.target.value,
                                            }))
                                        }
                                    >
                                        <option value="">선택해 주세요</option>
                                        {choices[term.key].map((value) => (
                                            <option key={value} value={value}>
                                                {choiceLabels[value] ?? value}
                                            </option>
                                        ))}
                                    </select>
                                ) : Array.isArray(term.value) ? (
                                    <p className="mt-2">
                                        구간별 RS는 MVP 계산을 지원하지 않습니다.
                                    </p>
                                ) : (
                                    <input
                                        className="mt-2 w-full rounded-lg border border-stone-300 p-2"
                                        type="text"
                                        inputMode={
                                            term.key === "mg_amount" || term.key === "rs_rate"
                                                ? "decimal"
                                                : "text"
                                        }
                                        value={
                                            edits[term.key] ??
                                            (typeof term.value === "string" ? term.value : "")
                                        }
                                        onChange={(event) =>
                                            setEdits((previous) => ({
                                                ...previous,
                                                [term.key]: event.target.value,
                                            }))
                                        }
                                    />
                                )}
                                {term.key === "mg_amount" && (
                                    <span className="mt-1 block text-sm text-stone-600">
                                        원 단위로 입력해 주세요.
                                    </span>
                                )}
                                {term.key === "rs_rate" && (
                                    <span className="mt-1 block text-sm text-stone-600">
                                        비율을 0~1로 입력해 주세요. 예를 들어 60%는 0.6입니다.
                                    </span>
                                )}
                            </label>
                        )}

                        {edits[term.key] !== undefined && term.quote && (
                            <p className="text-sm text-stone-600">
                                아래 인용은 최초 추출 시 참고한 계약서 문구입니다.
                                수정한 값과 일치하는지 확인해 주세요.
                            </p>
                        )}
                        {term.key === "deductions" && (
                            <div className="space-y-3">
                                {deductions.map((item, index) => (
                                    <fieldset
                                        key={index}
                                        className="space-y-3 rounded-lg border border-stone-300 p-4"
                                    >
                                        <legend className="px-1 text-sm">공제 항목 {index + 1}</legend>

                                        <label className="block">
                                            항목 이름
                                            <input
                                                className="mt-1 w-full rounded-lg border border-stone-300 p-2"
                                                value={item.name}
                                                onChange={(event) =>
                                                    updateDeduction(index, { name: event.target.value })
                                                }
                                            />
                                        </label>

                                        <label className="block">
                                            입력 방식
                                            <select
                                                className="mt-1 w-full rounded-lg border border-stone-300 p-2"
                                                value={item.amount != null ? "amount" : "rate"}
                                                onChange={(event) =>
                                                    updateDeduction(
                                                        index,
                                                        event.target.value === "amount"
                                                            ? { amount: "", rate: null }
                                                            : { rate: "", amount: null }
                                                    )
                                                }
                                            >
                                                <option value="rate">비율</option>
                                                <option value="amount">금액</option>
                                            </select>
                                        </label>

                                        <label className="block">
                                            {item.amount != null ? "금액 (원)" : "비율 (0~1)"}
                                            <input
                                                type="text"
                                                inputMode="decimal"
                                                className="mt-1 w-full rounded-lg border border-stone-300 p-2"
                                                value={item.amount ?? item.rate ?? ""}
                                                onChange={(event) =>
                                                    updateDeduction(
                                                        index,
                                                        item.amount != null
                                                            ? { amount: event.target.value, rate: null }
                                                            : { rate: event.target.value, amount: null }
                                                    )
                                                }
                                            />
                                            {item.amount == null && (
                                                <span className="mt-1 block text-sm text-stone-600">
                                                    예를 들어 10%는 0.1로 입력해 주세요.
                                                </span>
                                            )}
                                        </label>

                                        <button
                                            type="button"
                                            className="rounded-lg border border-stone-300 px-3 py-2"
                                            onClick={() =>
                                                setDeductionEdits(
                                                    deductions.filter((_, itemIndex) => itemIndex !== index)
                                                )
                                            }
                                        >
                                            이 항목 삭제
                                        </button>
                                    </fieldset>
                                ))}

                                <button
                                    type="button"
                                    className="rounded-lg border border-stone-300 px-3 py-2"
                                    onClick={() =>
                                        setDeductionEdits([
                                            ...deductions,
                                            { name: "", rate: "", amount: null },
                                        ])
                                    }
                                >
                                    공제 항목 추가
                                </button>
                            </div>
                        )}
                        {term.quote ? (
                            <blockquote className="whitespace-pre-wrap break-words border-l-2 border-stone-300 pl-3">
                                <span className="mb-2 block text-sm font-medium">
                                    근거 조항 · {term.source_clause_id}
                                </span>
                                {term.quote}
                            </blockquote>
                        ) : (
                            <p className="text-sm text-stone-600">
                                연결된 근거 조항이 없습니다.
                            </p>
                        )}
                        {response.unconfirmed_required.includes(term.key) && (
                            <label className="flex items-start gap-2 border-t border-stone-200 pt-4">
                                <input
                                    type="checkbox"
                                    className="mt-1"
                                    checked={
                                        checkedValues[term.key] ===
                                        confirmationValue(term.key, term.value)
                                    }
                                    onChange={(event) =>
                                        setCheckedValues((previous) => ({
                                            ...previous,
                                            [term.key]: event.target.checked
                                                ? confirmationValue(term.key, term.value)
                                                : "",
                                        }))
                                    }
                                />
                                <span>계약서와 이 값을 확인했습니다.</span>
                            </label>
                        )}
                        {showErrors && (
                            <div role="alert" className="space-y-1 text-sm">
                                <p>
                                    {validationMessage(
                                        term.key,
                                        currentValue(term.key, term.value)
                                    )}
                                </p>

                                {requiredKeys.includes(term.key) &&
                                    checkedValues[term.key] !==
                                    confirmationValue(term.key, term.value) && (
                                        <p>값과 근거를 확인하고 체크해 주세요.</p>
                                    )}
                            </div>
                        )}
                    </article>
                ))}
                <section className="space-y-3 rounded-2xl bg-white p-6">
                    <button
                        type="button"
                        className="rounded-lg bg-teal-900 px-4 py-2 text-white"
                        onClick={prepareConfirmation}
                    >
                        확정 요청 확인
                    </button>
                    <label className="block">
                        개발 확인용 저장 응답
                        <select
                            className="mt-2 w-full rounded-lg border border-stone-300 p-2"
                            value={saveMode}
                            onChange={(event) => {
                                setSaveMode(event.target.value as "success" | "invalid");
                                setSavedSnapshot(null);
                                setSaveMessage("");
                            }}
                        >
                            <option value="success">저장 성공 · 샘플 A 원래 값</option>
                            <option value="invalid">저장 실패 · INVALID_TERM</option>
                        </select>
                    </label>

                    <button
                        type="button"
                        className="rounded-lg border border-stone-300 px-4 py-2"
                        onClick={saveMockResponse}
                    >
                        저장 응답 확인
                    </button>

                    {saveMessage && <p role="status">{saveMessage}</p>}

                    <button
                        type="button"
                        disabled={!canContinue}
                        className="rounded-lg bg-teal-900 px-4 py-2 text-white disabled:opacity-40"
                        onClick={() => {
                            if (canContinue) {
                                router.push("/statements");
                            }
                        }}
                    >
                        정산서 입력으로
                    </button>

                    {showErrors && response.missing_keys.length > 0 && (
                        <p role="alert">
                            응답에 빠진 조건이 있습니다. 조건을 다시 불러와 주세요.
                        </p>
                    )}

                    {requestPreview && (
                        <details open>
                            <summary>개발 확인용 요청 본문 · 버튼을 누른 시점의 값</summary>
                            <pre className="mt-3 overflow-auto whitespace-pre-wrap text-sm">
                                {requestPreview}
                            </pre>
                        </details>
                    )}
                </section></div>
        </main>
    );
}