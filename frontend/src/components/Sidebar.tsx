"use client";

import { FileText, LogOut, Menu, MoreHorizontal, Plus, Search, Trash2, X } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, errorText, setToken, type ContractOut, type UserOut } from "../lib/api";
import { buttonClass } from "../lib/ui";
import { useContracts } from "./ShellContext";

// 항목을 누르면 상태에 따라: 조건 확인 대기 → 조건, 확정 → 결과, 처리중 → 조건(읽는 중 화면), 처리 실패 → 첫 화면
export function contractHref(c: ContractOut) {
  if (c.status === "확정") return `/results?id=${c.id}`;
  if (c.status === "처리 실패") return "/";
  return `/terms?id=${c.id}`;
}

type Props = { currentId?: string; me?: UserOut | null; loading?: boolean };

export function Sidebar(props: Props) {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <>
      {/* 좁은 화면(768px 미만): 상단 바 + 왼쪽 서랍 */}
      <header className="sticky top-0 z-20 -mx-4 flex items-center gap-2.5 border-b border-line-soft bg-card px-4 py-3 md:hidden">
        <button
          type="button"
          aria-label={open ? "내 계약서 목록 닫기" : "내 계약서 목록 열기"}
          aria-expanded={open}
          aria-controls="side-nav"
          onClick={() => setOpen((v) => !v)}
          className="grid size-11 place-items-center rounded-btn bg-surface"
        >
          {open ? <X size={18} /> : <Menu size={18} />}
        </button>
        <Link href="/" className="text-[15px] font-extrabold tracking-[0.2em]">
          OPENBOOK
        </Link>
        <Link href="/" aria-label="계약서 올리기" className="ml-auto grid size-11 place-items-center rounded-btn bg-accent text-white">
          <Plus size={18} strokeWidth={2.4} />
        </Link>
      </header>
      {open && <div aria-hidden className="fixed inset-0 z-30 bg-ink/30 md:hidden" onClick={() => setOpen(false)} />}

      <aside
        id="side-nav"
        className={`${open ? "flex" : "hidden"} fixed inset-y-0 left-0 z-40 w-[300px] max-w-[85vw] flex-col overflow-y-auto rounded-r-card bg-card shadow-window md:static md:z-auto md:flex md:w-[240px] md:max-w-none md:shrink-0 md:overflow-visible md:rounded-card md:shadow-card lg:w-[280px]`}
      >
        <SidebarBody {...props} onNavigate={() => setOpen(false)} />
      </aside>
    </>
  );
}

function SidebarBody({ currentId = "", me = null, loading = false, onNavigate }: Props & { onNavigate: () => void }) {
  const router = useRouter();
  const { contracts, reloadContracts } = useContracts();
  const [menuFor, setMenuFor] = useState<string | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!menuFor) return;
    const close = () => setMenuFor(null);
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && close();
    window.addEventListener("click", close);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("click", close);
      window.removeEventListener("keydown", onKey);
    };
  }, [menuFor]);

  async function remove(c: ContractOut) {
    setMenuFor(null);
    if (!window.confirm(`'${c.title}' 계약서와 정산 기록을 모두 삭제할까요? 되돌릴 수 없습니다.`)) return;
    try {
      await api(`/contracts/${c.id}`, { method: "DELETE" });
      setError("");
      await reloadContracts();
      if (c.id === currentId) router.push("/");
    } catch (e) {
      setError(errorText(e));
    }
  }

  async function logout() {
    try {
      await api("/auth/logout", { method: "POST" });
    } finally {
      setToken(null);
      router.push("/login");
    }
  }

  return (
    <div className="flex min-h-[860px] flex-1 flex-col gap-[18px] px-4 pb-4 pt-6 md:min-h-0">
      <Link href="/" onClick={onNavigate} className="flex items-baseline gap-2 px-2">
        <span className="text-[17px] font-extrabold tracking-[0.2em]">OPENBOOK</span>
        <span className="text-fine font-semibold text-muted">오픈북</span>
      </Link>

      {!loading && (
        <>
          <div className="flex items-center gap-2">
            <Link href="/" onClick={onNavigate} className={`${buttonClass("primary")} flex-1 !px-3 !text-sm`}>
              <Plus size={16} strokeWidth={2.4} aria-hidden />
              계약서 올리기
            </Link>
            {/* 이번엔 모양만: 검색은 아직 동작하지 않는다 */}
            <button type="button" aria-label="계약서 검색" aria-disabled="true" className="grid size-11 shrink-0 cursor-default place-items-center rounded-btn bg-black text-white">
              <Search size={17} strokeWidth={2.2} aria-hidden />
            </button>
          </div>

          <div className="h-px bg-line-soft" />
          <div className="flex items-center justify-between px-2 text-fine text-muted">
            <span className="font-semibold">내 계약서</span>
            {contracts && <span className="num">{contracts.length}건</span>}
          </div>

          <nav aria-label="내 계약서" className="flex flex-col gap-1">
            {contracts?.length === 0 && <p className="px-2 text-small text-muted">아직 올린 계약서가 없습니다.</p>}
            {contracts?.map((c) => {
              const current = c.id === currentId;
              return (
                <div key={c.id} className="relative flex items-start">
                  <Link
                    href={contractHref(c)}
                    onClick={onNavigate}
                    aria-current={current ? "page" : undefined}
                    className={`flex min-w-0 flex-1 items-start gap-2.5 rounded-field py-2.5 pl-3 pr-10 ${
                      current ? "bg-accent-soft text-accent" : "text-ink hover:bg-surface"
                    }`}
                  >
                    <FileText size={18} aria-hidden className="mt-0.5 shrink-0" />
                    <span className="flex min-w-0 flex-col gap-0.5">
                      <span className="truncate text-sm font-[650]">{c.title}</span>
                      <span className={`num text-fine ${current ? "text-ink-2" : "text-muted"}`}>
                        {c.status} · {c.uploaded_at.slice(0, 10)}
                      </span>
                    </span>
                  </Link>
                  <button
                    type="button"
                    aria-label={`${c.title} 메뉴`}
                    aria-haspopup="menu"
                    aria-expanded={menuFor === c.id}
                    onClick={(e) => {
                      e.stopPropagation();
                      setMenuFor(menuFor === c.id ? null : c.id);
                    }}
                    className="absolute right-0.5 top-1 grid size-9 place-items-center rounded-btn text-muted hover:bg-line-soft"
                  >
                    <MoreHorizontal size={16} aria-hidden />
                  </button>
                  {menuFor === c.id && (
                    <div role="menu" className="absolute right-1 top-11 z-10 min-w-28 rounded-tile border border-line bg-card p-1 shadow-card">
                      <button
                        type="button"
                        role="menuitem"
                        onClick={() => remove(c)}
                        className="flex min-h-11 w-full items-center gap-2 rounded-field px-3 text-sm font-semibold text-ink hover:bg-surface"
                      >
                        <Trash2 size={15} aria-hidden />
                        삭제
                      </button>
                    </div>
                  )}
                </div>
              );
            })}
            {error && (
              <p role="alert" className="px-2 text-small text-error">
                {error}
              </p>
            )}
          </nav>

          <div className="flex-1" />
          <div className="h-px bg-line-soft" />
          <p className="px-2 text-fine leading-[1.55] text-muted">계약서·정산서는 언제든 삭제할 수 있어요. 원본 파일은 서버에 보관하지 않습니다.</p>
          {me && (
            <div className="flex items-center gap-2.5 rounded-field border border-line-soft p-2">
              <span aria-hidden className="grid size-8 shrink-0 place-items-center rounded-field bg-accent-soft text-small font-extrabold text-accent">
                {me.auth_disabled ? "로" : (me.email[0] ?? "").toUpperCase()}
              </span>
              <span className="flex min-w-0 flex-1 flex-col">
                <span className="truncate text-[13px] font-[650]">{me.auth_disabled ? "로컬 사용자" : me.email}</span>
                {me.auth_disabled && <span className="text-fine text-muted">로컬 모드 · 로그인 꺼짐</span>}
              </span>
              {!me.auth_disabled && (
                <button type="button" aria-label="로그아웃" onClick={logout} className="grid size-9 shrink-0 place-items-center rounded-btn text-muted hover:bg-line-soft">
                  <LogOut size={16} aria-hidden />
                </button>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
