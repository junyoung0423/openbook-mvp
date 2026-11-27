"use client";

import type { InputHTMLAttributes } from "react";
import { formatMoneyInput, stripMoney } from "../lib/format";

type Props = Omit<InputHTMLAttributes<HTMLInputElement>, "value" | "onChange" | "type" | "inputMode"> & {
  // 콤마 없는 문자열("3000000"). 서버로 보내는 값도 이 문자열 그대로다
  value: string;
  onChange: (value: string) => void;
  allowNegative?: boolean;
  className?: string;
};

// 화면에는 `3,000,000 원`으로 보이고, 들고 있는 값은 콤마 없는 문자열이다. 숫자 타입으로 바꾸지 않는다.
export function MoneyInput({ value, onChange, allowNegative = false, className = "", ...rest }: Props) {
  return (
    <span
      className={`mt-1.5 flex min-h-[46px] items-center rounded-field border border-field bg-card px-3.5 focus-within:ring-2 focus-within:ring-accent ${className}`}
    >
      <input
        {...rest}
        type="text"
        // 음수를 받을 때는 '-'를 칠 수 있는 키보드가 필요하다
        inputMode={allowNegative ? "text" : "decimal"}
        autoComplete="off"
        value={formatMoneyInput(value)}
        onChange={(e) => onChange(stripMoney(e.target.value, allowNegative))}
        className="num min-w-0 flex-1 bg-transparent py-2 text-right text-base text-ink outline-none"
      />
      <span aria-hidden className="ml-1.5 text-[15px] text-muted">
        원
      </span>
    </span>
  );
}
