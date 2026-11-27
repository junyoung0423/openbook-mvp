import type { ButtonHTMLAttributes, ReactNode } from "react";
import { buttonClass, type ButtonVariant } from "../lib/ui";

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  // disabled일 때 옆에 보여 줄 이유 문구
  disabledReason?: ReactNode;
};

export function Button({ variant = "primary", disabledReason, className = "", type = "button", ...rest }: Props) {
  const button = <button type={type} className={`${buttonClass(variant)} ${className}`} {...rest} />;
  if (!rest.disabled || !disabledReason) return button;
  return (
    <span className="inline-flex flex-wrap items-center gap-x-3 gap-y-1">
      {button}
      <span className="text-small text-muted">{disabledReason}</span>
    </span>
  );
}
