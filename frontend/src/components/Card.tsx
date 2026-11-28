import type { ComponentProps, ReactNode } from "react";

// 흰 카드 (모서리 10, 옅은 그림자)
export function Card({ className = "", ...rest }: ComponentProps<"section">) {
  return <section className={`rounded-card bg-card p-5 shadow-card md:px-7 md:py-6 ${className}`} {...rest} />;
}

type HeaderProps = {
  title: ReactNode;
  description?: ReactNode;
  // 제목 줄 오른쪽에 둘 동작(버튼 등)
  actions?: ReactNode;
  as?: "h1" | "h2" | "h3";
};

export function CardHeader({ title, description, actions, as: Heading = "h2" }: HeaderProps) {
  return (
    <header className="mb-4 flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
      <div className="min-w-0">
        <Heading className="text-title font-[750] leading-snug">{title}</Heading>
        {description && <p className="mt-1 text-[15px] leading-relaxed text-ink-2">{description}</p>}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
    </header>
  );
}
