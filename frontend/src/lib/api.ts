import { buttonClass, fieldClass } from "./ui";

// 오픈북 API 클라이언트. 금액·비율은 항상 문자열로 주고받는다.
// 로그인하면 받은 토큰을 Authorization: Bearer로 보낸다. 토큰이 없거나 만료되면 로그인 화면으로 보낸다.

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const TOKEN_KEY = "openbook-token";

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
  }
}

function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string | null) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    // 저장소를 쓸 수 없는 브라우저: 이번 화면에서만 로그인 상태가 유지되지 않는다
  }
}

function goToLogin() {
  const here = window.location.pathname + window.location.search;
  // 컴포넌트 밖의 공용 함수라 router를 쓸 수 없다. 로그인 화면으로 새로 연다
  // eslint-disable-next-line @next/next/no-location-assign-relative-destination
  if (window.location.pathname !== "/login") window.location.assign(`/login?next=${encodeURIComponent(here)}`);
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
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
    if (detail?.code === "UNAUTHENTICATED") {
      setToken(null);
      goToLogin();
    }
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

export type UserOut = { id: string; email: string; auth_disabled?: boolean };
export type LoginOut = { token: string; user: UserOut };

export type ContractOut ={ id: string; title: string; status: string; uploaded_at: string };
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

// 지급내역형 정산서: 매출액 → 회사입금액 → 정산액 → 원천징수 → 작가지급액
export type StatementBody = {
  period_start: string;
  period_end: string;
  gross: string;
  net_revenue: string | null;
  deductions: { name: string; amount: string }[];
  reported_settlement: string | null;
  reported_withholding: string | null;
  reported_payout: string;
};
export type StatementOut = StatementBody & { id: string };
export type StatementDraft = Partial<Omit<StatementBody, "deductions">> & {
  rows?: {
  line: number;
  label: string;
  value: string;
  field: string | null;
  note?: string | null;
}[];
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
  computed_settlement: string | null;
  reported_settlement: string | null;
  settlement_diff: string | null;
  payout_before_tax: string | null;
  computed_withholding: string | null;
  reported_withholding: string | null;
  withholding_diff: string | null;
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
  unsupported_reason: string | null;
  diff_meaning: string;
  notice: string;
};

export type Citation = {
  source: "contract" | "standard" | "law";
  clause_id: string;
  clause_no: string | null;
  clause_title: string | null;
  quote: string;
  law_name?: string | null; // source=law일 때
  effective_date?: string | null; // 원문 시행일 (YYYY-MM-DD)
  source_url?: string | null;
};
export type QAResult = {
  contract_id: string;
  question: string;
  found: boolean;
  answer: string;
  citations: Citation[];
  basis: string | null;
  notice: string;
  warnings: string[];
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
export const SIGNED_MONEY = /^-?[0-9]+(\.[0-9]+)?$/;
export const RATE = /^(0(\.[0-9]+)?|1(\.0+)?)$/;

export { won } from "./format";

// 아직 옛 방식으로 쓰는 화면용 별칭. 새 화면은 components/Button과 lib/ui를 쓴다.
export const field = fieldClass;
export const primary = buttonClass("primary");
export const secondary = buttonClass("secondary");
