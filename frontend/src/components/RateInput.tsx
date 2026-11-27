"use client";

import { useId, useState, type InputHTMLAttributes } from "react";
import { percentToRate, rateToPercent } from "../lib/format";
import { fieldClass } from "../lib/ui";

type Props = Omit<InputHTMLAttributes<HTMLInputElement>, "value" | "onChange" | "type" | "inputMode"> & {
  // 0~1 비율 문자열("0.65"). 서버로 보내는 값도 이 문자열 그대로다. 빈 문자열은 값 없음
  value: string;
  onChange: (rate: string) => void;
};

const cleanPercent = (s: string) => {
  const digits = s.replace(/[^0-9.]/g, "");
  const dot = digits.indexOf(".");
  return dot < 0 ? digits : digits.slice(0, dot + 1) + digits.slice(dot + 1).replace(/\./g, "");
};
// 입력 도중의 "6."은 6으로 본다
const toRate = (text: string) => percentToRate(text.endsWith(".") ? text.slice(0, -1) : text);

// 작가는 `65`를 입력하고 화면에는 `65 %`, 상태·서버에는 `"0.65"`가 간다.
// 범위를 벗어났거나 읽을 수 없는 입력은 빈 값("")을 올려 보내고, 입력칸에 안내를 보인다.
export function RateInput({ value, onChange, className = "", ...rest }: Props) {
  const hintId = useId();
  const [text, setText] = useState(() => rateToPercent(value) ?? "");
  const [seen, setSeen] = useState(value);

  // 위에서 값이 바뀌었을 때(서버에서 불러온 값 등)만 입력칸 글자를 맞춘다
  if (value !== seen) {
    setSeen(value);
    if (value !== (toRate(text) ?? "")) setText(rateToPercent(value) ?? "");
  }

  const invalid = text !== "" && toRate(text) === null;

  return (
    <span className="mt-1 block">
      <span className="relative block">
        <input
          {...rest}
          type="text"
          inputMode="decimal"
          autoComplete="off"
          value={text}
          aria-invalid={invalid || undefined}
          aria-describedby={invalid ? hintId : rest["aria-describedby"]}
          onChange={(e) => {
            const next = cleanPercent(e.target.value);
            const rate = toRate(next) ?? "";
            setText(next);
            setSeen(rate);
            onChange(rate);
          }}
          className={`${fieldClass} num !mt-0 pr-9 text-right ${className}`}
        />
        <span aria-hidden className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-muted">
          %
        </span>
      </span>
      {invalid && (
        <span id={hintId} role="alert" className="mt-1 block text-small text-error">
          0 이상 100 이하의 숫자로 입력해 주세요.
        </span>
      )}
    </span>
  );
}
