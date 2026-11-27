// 버튼·입력칸 클래스. 컴포넌트(Button 등)와 아직 옛 방식을 쓰는 화면이 같은 모양을 쓰도록 한 곳에 둔다.

export type ButtonVariant = "primary" | "secondary" | "ghost";

const buttonBase =
  "inline-flex min-h-11 items-center justify-center gap-2 rounded-control px-4 py-2 font-medium " +
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-2 " +
  "disabled:cursor-not-allowed disabled:opacity-50";

const buttonVariants: Record<ButtonVariant, string> = {
  primary: "bg-brand text-white hover:bg-brand/90",
  secondary: "border border-line bg-surface text-ink hover:bg-paper",
  ghost: "text-muted hover:bg-paper hover:text-ink",
};

export const buttonClass = (variant: ButtonVariant) => `${buttonBase} ${buttonVariants[variant]}`;

export const fieldClass =
  "mt-1 block min-h-11 w-full rounded-control border border-line bg-surface p-2 text-ink " +
  "placeholder:text-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand";
