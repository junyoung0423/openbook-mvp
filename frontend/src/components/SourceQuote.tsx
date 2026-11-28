"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";

// 근거 원문 블록. 원문은 줄이거나 바꾸지 않고, 6줄을 넘으면 접어 두었다가 "전체 보기"로 펼친다.
export function SourceQuote({
  label,
  children,
  className = "",
  prefix = "근거 · ",
}: {
  label: ReactNode;
  children: string;
  className?: string;
  // 라벨 앞에 붙는 말. 근거 조항이 없을 때는 ""로 두고 label을 "근거 조항"으로 쓴다
  prefix?: string;
}) {
  const body = useRef<HTMLParagraphElement>(null);
  const [expanded, setExpanded] = useState(false);
  const [overflowing, setOverflowing] = useState(false);

  useEffect(() => {
    const el = body.current;
    if (!el) return;
    const measure = () => {
      // 접힌 상태일 때만 잘렸는지 잴 수 있다. 펼친 뒤에는 버튼을 그대로 둔다
      if (el.classList.contains("line-clamp-6")) setOverflowing(el.scrollHeight > el.clientHeight + 1);
    };
    const observer = new ResizeObserver(measure);
    observer.observe(el);
    return () => observer.disconnect();
  }, [children]);

  return (
    <figure className={`flex flex-col gap-1.5 rounded-tile bg-quote px-[18px] py-4 ${className}`}>
      <figcaption className="text-fine font-bold text-accent">
        {prefix}
        {label}
      </figcaption>
      <blockquote>
        <p ref={body} className={`whitespace-pre-wrap text-[14px] leading-[1.7] text-ink ${expanded ? "" : "line-clamp-6"}`}>
          {children}
        </p>
      </blockquote>
      {(overflowing || expanded) && (
        <button
          type="button"
          aria-expanded={expanded}
          onClick={() => setExpanded((v) => !v)}
          className="inline-flex min-h-11 items-center self-start text-small font-semibold text-accent underline underline-offset-2"
        >
          {expanded ? "접기" : "전체 보기"}
        </button>
      )}
    </figure>
  );
}
