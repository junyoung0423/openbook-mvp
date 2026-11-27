// 금액·비율 표시와 입력 변환. 전부 문자열 조작이다: 숫자 타입으로 바꿔 계산하지 않는다.
// 틀리면 금액이 틀어지는 곳이라 format.test.ts가 함께 있다.

// 서버가 준 금액 문자열에 천 단위 콤마와 '원'을 붙인다. 반올림·축약은 하지 않는다.
export function won(value: string | null | undefined): string {
  if (value == null) return "—";
  const negative = value.startsWith("-");
  const [whole, fraction] = value.replace("-", "").split(".");
  const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return `${negative ? "-" : ""}${grouped}${fraction ? `.${fraction}` : ""}원`;
}

// 입력칸에 쓰인 글자에서 콤마·공백·'원' 등을 지우고 숫자·소수점(·허용할 때만 맨 앞 '-')만 남긴다.
// "1,234,567원" → "1234567". 입력 도중의 "-"나 "12."도 그대로 돌려준다(저장 때 규칙으로 검사).
export function stripMoney(input: string, allowNegative = false): string {
  const negative = allowNegative && input.trim().startsWith("-");
  const digits = input.replace(/[^0-9.]/g, "");
  const dot = digits.indexOf(".");
  const single = dot < 0 ? digits : digits.slice(0, dot + 1) + digits.slice(dot + 1).replace(/\./g, "");
  return (negative ? "-" : "") + single;
}

// stripMoney를 거친 문자열을 입력칸에 보일 모양(천 단위 콤마)으로 바꾼다. 소수점 아래는 그대로 둔다.
export function formatMoneyInput(raw: string): string {
  const negative = raw.startsWith("-");
  const body = negative ? raw.slice(1) : raw;
  const dot = body.indexOf(".");
  const whole = dot < 0 ? body : body.slice(0, dot);
  const rest = dot < 0 ? "" : body.slice(dot);
  return (negative ? "-" : "") + whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",") + rest;
}

const trimZeros = (s: string) => s.replace(/0+$/, "");

// 퍼센트 문자열 → 0~1 비율 문자열(소수점을 두 자리 왼쪽으로). "65" → "0.65", "100" → "1".
// 0~100 밖, 빈 문자열, 숫자가 아닌 값은 null.
export function percentToRate(percent: string): string | null {
  const m = /^([0-9]+)(?:\.([0-9]+))?$/.exec(percent.trim());
  if (!m) return null;
  const whole = m[1].replace(/^0+(?=[0-9])/, "");
  const fraction = m[2] ?? "";
  if (whole.length > 3 || (whole.length === 3 && (whole !== "100" || trimZeros(fraction) !== ""))) return null;
  const padded = whole.padStart(2, "0");
  const intPart = padded.slice(0, -2).replace(/^0+(?=[0-9])/, "") || "0";
  const frac = trimZeros(padded.slice(-2) + fraction);
  return frac ? `${intPart}.${frac}` : intPart;
}

// 0~1 비율 문자열 → 퍼센트 문자열(소수점을 두 자리 오른쪽으로). "0.65" → "65", "0.065" → "6.5".
// 0~1 밖이거나 숫자가 아니면 null.
export function rateToPercent(rate: string): string | null {
  const m = /^(0|1)(?:\.([0-9]+))?$/.exec(rate.trim());
  if (!m) return null;
  const fraction = m[2] ?? "";
  if (m[1] === "1" && trimZeros(fraction) !== "") return null;
  const padded = fraction.padEnd(2, "0");
  const intPart = (m[1] + padded.slice(0, 2)).replace(/^0+(?=[0-9])/, "");
  const frac = trimZeros(padded.slice(2));
  return frac ? `${intPart}.${frac}` : intPart;
}

// 서버가 준 날짜시간 문자열("2026-11-27T03:30:53")을 "11월 27일"로 줄인다. 문자열 조작만 쓰고, 모양이 다르면 그대로 돌려준다.
export function shortDate(iso: string): string {
  const m = /^[0-9]{4}-([0-9]{2})-([0-9]{2})/.exec(iso);
  return m ? `${m[1].replace(/^0/, "")}월 ${m[2].replace(/^0/, "")}일` : iso;
}
