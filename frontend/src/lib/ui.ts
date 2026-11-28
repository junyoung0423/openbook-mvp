// 버튼·입력칸 클래스. 컴포넌트(Button 등)와 아직 옛 방식을 쓰는 화면이 같은 모양을 쓰도록 한 곳에 둔다.

export type ButtonVariant = "primary" | "dark" | "secondary" | "ghost";

const buttonBase =
  "inline-flex min-h-11 items-center justify-center gap-2 rounded-btn px-5 py-2 text-[15px] font-bold " +
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 " +
  "disabled:cursor-not-allowed disabled:bg-locked disabled:text-white disabled:border-transparent";

const buttonVariants: Record<ButtonVariant, string> = {
  primary: "bg-accent text-white hover:bg-accent-hover",
  dark: "bg-black text-white hover:bg-black/85",
  secondary: "border border-field bg-card text-ink hover:bg-surface",
  ghost: "px-3 font-semibold text-ink-2 hover:bg-line-soft disabled:bg-transparent disabled:text-muted",
};

export const buttonClass = (variant: ButtonVariant) => `${buttonBase} ${buttonVariants[variant]}`;

export const fieldClass =
  "mt-1.5 block min-h-[46px] w-full rounded-field border border-field bg-card px-3.5 py-2 text-[15px] text-ink " +
  "placeholder:text-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent";
