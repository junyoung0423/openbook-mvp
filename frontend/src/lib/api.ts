// 오픈북 API 클라이언트. 금액·비율은 항상 문자열로 주고받는다.
// 임시 인증: 브라우저마다 만든 id를 X-User-Id로 보낸다 (로그인이 붙으면 교체).

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
  }
}

function userId(): string {
  const key = "openbook-user-id";
  try {
    let id = localStorage.getItem(key);
    if (!id) {
      id = crypto.randomUUID();
      localStorage.setItem(key, id);
    }
    return id;
  } catch {
    return "anonymous-browser";
  }
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("X-User-Id", userId());
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { ...init, headers });
  } catch {
    throw new ApiError(0, "NETWORK", "서버에 연결하지 못했습니다. 잠시 후 다시 시도해 주세요.");
  }
  if (res.status === 204) return undefined as T;
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const detail = body?.detail;
    if (detail && typeof detail === "object" && !Array.isArray(detail)) {
      throw new ApiError(res.status, detail.code, detail.message);
    }
    throw new ApiError(res.status, "INVALID_REQUEST", "입력값을 확인해 주세요.");
  }
  return body as T;
}

export const errorText = (e: unknown) =>
  e instanceof ApiError ? e.message : "알 수 없는 오류가 났습니다. 다시 시도해 주세요.";

// ---------------------------------------------------------------- 응답 타입

export type ContractOut = { id: string; title: string; status: string; uploaded_at: string };
export type Clause = { id: string; no: string | null; title: string | null; text: string };

export type Deduction = { name: string; rate?: string | null; amount?: string | null };
export type Term = {
  key: string;
  value: unknown;
  status: "extracted" | "not_found" | "user_input";
  source_clause_id: string | null;
  quote: string | null;
  confirmed: boolean;
  confirmed_at: string | null;
};
export type TermsResponse = {
  contract_id: string;
  terms: Term[];
  missing_keys: string[];
  unconfirmed_required: string[];
  all_confirmed: boolean;
};

export type StatementBody = {
  period_start: string;
  period_end: string;
  gross: string;
  deductions: { name: string; amount: string }[];
  reported_payout: string;
};
export type StatementOut = StatementBody & { id: string };
export type StatementDraft = Partial<Omit<StatementBody, "deductions">> & {
  deductions: { name: string; amount: string }[];
  missing: string[];
  warnings: string[];
};

export type CalcStep = {
  key: string;
  label: string;
  value: string;
  formula: string | null;
  source_clause_id: string | null;
};
export type PeriodReconciliation = {
  statement_id: string;
  period_start: string;
  period_end: string;
  status: "computed" | "unsupported";
  computed_payout: string | null;
  reported_payout: string;
  diff: string | null;
  mg_balance_after: string | null;
  breakdown: CalcStep[];
  unsupported_reason: string | null;
  summary: string;
  questions: string[];
};
export type ReconciliationReport = {
  contract_id: string;
  items: PeriodReconciliation[];
  rules_version: string;
  diff_meaning: string;
  notice: string;
};

// ---------------------------------------------------------------- 표시

export const TERM_LABELS: Record<string, string> = {
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

export const CHOICES: Record<string, Record<string, string>> = {
  mg_recoup: { from_rs: "RS에서 차감", separate: "별도 처리", unknown: "확인 필요" },
  mg_carryover: { carry_over: "이월", refund: "반환", forgiven: "반환 요구 없음", unknown: "확인 필요" },
  revenue_base: { gross: "총매출", net: "순매출", other: "기타" },
  settlement_cycle: { monthly: "월별", quarterly: "분기별", semiannual: "반기별", other: "기타" },
};

export const MONEY = /^[0-9]+(\.[0-9]+)?$/;
export const RATE = /^(0(\.[0-9]+)?|1(\.0+)?)$/;

export function won(value: string | null | undefined): string {
  if (value == null) return "—";
  const negative = value.startsWith("-");
  const [whole, fraction] = value.replace("-", "").split(".");
  const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return `${negative ? "-" : ""}${grouped}${fraction ? `.${fraction}` : ""}원`;
}

export const field = "mt-1 block w-full rounded-lg border border-stone-300 bg-white p-2";
export const primary =
  "rounded-lg bg-teal-900 px-4 py-2 text-white disabled:cursor-not-allowed disabled:opacity-50";
export const secondary = "rounded-lg border border-stone-300 bg-white px-3 py-2";
