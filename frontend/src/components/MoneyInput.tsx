"use client";

import type { InputHTMLAttributes } from "react";
import { formatMoneyInput, stripMoney } from "../lib/format";
import { fieldClass } from "../lib/ui";

type Props = Omit<InputHTMLAttributes<HTMLInputElement>, "value" | "onChange" | "type" | "inputMode"> & {
  // 콤마 없는 문자열("3000000"). 서버로 보내는 값도 이 문자열 그대로다
  value: string;
  onChange: (value: string) => void;
  allowNegative?: boolean;
};

// 화면에는 `3,000,000 원`으로 보이고, 들고 있는 값은 콤마 없는 문자열이다. Number로 바꾸지 않는다.
export function MoneyInput({ value, onChange, allowNegative = false, className = "", ...rest }: Props) {
  return (
    <span className="relative mt-1 block">
      <input
        {...rest}
        type="text"
        // 음수를 받을 때는 '-'를 칠 수 있는 키보드가 필요하다
        inputMode={allowNegative ? "text" : "decimal"}
        autoComplete="off"
        value={formatMoneyInput(value)}
        onChange={(e) => onChange(stripMoney(e.target.value, allowNegative))}
        className={`${fieldClass} num !mt-0 pr-9 text-right ${className}`}
      />
      <span aria-hidden className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-muted">
        원
      </span>
    </span>
  );
}
