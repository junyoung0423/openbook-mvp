import type { HTMLAttributes, ReactNode } from "react";

export function Card({ className = "", ...rest }: HTMLAttributes<HTMLElement>) {
  return <section className={`rounded-card border border-line bg-surface p-4 shadow-card sm:p-6 ${className}`} {...rest} />;
}

type HeaderProps = {
  title: ReactNode;
  description?: ReactNode;
  // 제목 줄 오른쪽에 둘 동작(버튼 등)
  actions?: ReactNode;
  as?: "h1" | "h2" | "h3";
};

export function CardHeader({ title, description, actions, as: Heading = "h2" }: HeaderProps) {
  const size = Heading === "h1" ? "text-page" : Heading === "h2" ? "text-section" : "text-card";
  return (
    <header className="mb-4 flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
      <div className="min-w-0">
        <Heading className={`${size} font-bold leading-snug`}>{title}</Heading>
        {description && <p className="mt-1 text-muted">{description}</p>}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
    </header>
  );
}
