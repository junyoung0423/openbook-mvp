"use client";

import type { InputHTMLAttributes } from "react";
import { formatMoneyInput, stripMoney } from "../lib/format";

type Props = Omit<InputHTMLAttributes<HTMLInputElement>, "value" | "onChange" | "type" | "inputMode" | "size"> & {
  // 콤마 없는 문자열("3000000"). 서버로 보내는 값도 이 문자열 그대로다
  value: string;
  onChange: (value: string) => void;
  allowNegative?: boolean;
  // lg: 정산서의 작가지급액처럼 가장 중요한 칸 (인디고 테두리, 큰 글자)
  size?: "md" | "lg";
  className?: string;
};

// 화면에는 `3,000,000 원`으로 보이고, 들고 있는 값은 콤마 없는 문자열이다. 숫자 타입으로 바꾸지 않는다.
export function MoneyInput({ value, onChange, allowNegative = false, size = "md", className = "", ...rest }: Props) {
  const lg = size === "lg";
  return (
    <span
      className={`mt-1.5 flex items-center rounded-field bg-card focus-within:ring-2 focus-within:ring-accent ${
        lg ? "min-h-[54px] border-[1.5px] border-accent px-4" : "min-h-[46px] border border-field px-3.5"
      } ${className}`}
    >
      <input
        {...rest}
        type="text"
        // 음수를 받을 때는 '-'를 칠 수 있는 키보드가 필요하다
        inputMode={allowNegative ? "text" : "decimal"}
        autoComplete="off"
        value={formatMoneyInput(value)}
        onChange={(e) => onChange(stripMoney(e.target.value, allowNegative))}
        className={`num min-w-0 flex-1 bg-transparent py-2 text-right text-ink outline-none ${lg ? "text-xl font-bold" : "text-base"}`}
      />
      <span aria-hidden className={`ml-1.5 text-muted ${lg ? "text-base" : "text-[15px]"}`}>
        원
      </span>
    </span>
  );
}
