"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";

// 근거 원문 블록. 원문은 줄이거나 바꾸지 않고, 6줄을 넘으면 접어 두었다가 "전체 보기"로 펼친다.
export function SourceQuote({ label, children, className = "" }: { label: ReactNode; children: string; className?: string }) {
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
    <figure className={`rounded-r-control border-l-2 border-brand bg-quote py-3 pr-4 pl-4 ${className}`}>
      <figcaption className="text-small font-medium text-muted">근거 · {label}</figcaption>
      <blockquote>
        <p ref={body} className={`mt-1 whitespace-pre-wrap ${expanded ? "" : "line-clamp-6"}`}>
          {children}
        </p>
      </blockquote>
      {(overflowing || expanded) && (
        <button
          type="button"
          aria-expanded={expanded}
          onClick={() => setExpanded((v) => !v)}
          className="mt-1 inline-flex min-h-11 items-center text-small font-medium text-brand underline underline-offset-2"
        >
          {expanded ? "접기" : "전체 보기"}
        </button>
      )}
    </figure>
  );
}
