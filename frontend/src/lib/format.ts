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

const DATE = /^[0-9]{4}-[0-9]{2}-[0-9]{2}$/;

// 한 달 전체(1일 ~ 말일)면 그 달의 연·월을 돌려준다. 아니면 null.
function wholeMonth(start: string, end: string): { year: string; month: string } | null {
  if (!DATE.test(start) || !DATE.test(end)) return null;
  if (!start.endsWith("-01") || start.slice(0, 7) !== end.slice(0, 7)) return null;
  // 말일인지: 다음 날이 1일이면 말일이다 (날짜 비교일 뿐 금액과 무관)
  const next = new Date(new Date(`${end}T00:00:00Z`).getTime() + 86_400_000);
  if (next.getUTCDate() !== 1) return null;
  return { year: start.slice(0, 4), month: start.slice(5, 7).replace(/^0/, "") };
}

// 기간 카드 제목: 한 달 전체면 "2027년 5월", 아니면 "2027-05-01 ~ 2027-05-20" 그대로
export function periodTitle(start: string, end: string): string {
  const m = wholeMonth(start, end);
  return m ? `${m.year}년 ${m.month}월` : `${start} ~ ${end}`;
}

// 월별 탭 이름: "5월" (여러 해에 걸치면 "2027년 5월"), 한 달 전체가 아니면 "05-01 ~ 05-20"
export function periodTab(start: string, end: string, withYear = false): string {
  const m = wholeMonth(start, end);
  if (m) return withYear ? `${m.year}년 ${m.month}월` : `${m.month}월`;
  return withYear ? `${start} ~ ${end}` : `${start.slice(5)} ~ ${end.slice(5)}`;
}
