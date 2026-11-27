"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { createContext, Suspense, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, setToken, type ContractOut, type UserOut } from "../lib/api";
import { buttonClass } from "../lib/ui";
import { StepNav, type Step } from "./StepNav";

type ContractState = { contract: ContractOut | null; reload: () => void };
const ContractContext = createContext<ContractState>({ contract: null, reload: () => {} });

// 지금 화면의 계약서(이름·상태). AppShell이 `GET /contracts/{id}`를 한 번 불러 둔다.
export const useContract = () => useContext(ContractContext);

const WIDTH = { narrow: "max-w-md", default: "max-w-3xl", wide: "max-w-5xl" } as const;

type Props = {
  children: ReactNode;
  // 계약서 화면이면 단계 표시에서 현재 위치를 가리킨다. 계약서 id(?id=)가 없으면 단계 표시는 나오지 않는다
  step?: Step;
  width?: keyof typeof WIDTH;
  // 로그인 화면처럼 사용자 정보를 불러오지 않는 화면
  bare?: boolean;
};

export function AppShell(props: Props) {
  // useSearchParams는 Suspense 안에서만 쓸 수 있다. 읽기 전에는 상단 바 뼈대만 보인다
  return (
    <Suspense fallback={<Frame width={props.width} header={<TopBar contract={null} me={null} bare />} body={null} />}>
      <ShellWithData {...props} />
    </Suspense>
  );
}

function Frame({
  width = "default",
  header,
  body,
}: {
  width?: keyof typeof WIDTH;
  header: ReactNode;
  body: ReactNode;
}) {
  return (
    <div className="min-h-screen bg-paper text-ink">
      {header}
      <main className={`mx-auto w-full ${WIDTH[width]} space-y-4 px-4 py-6 sm:px-6 sm:py-10`}>{body}</main>
    </div>
  );
}

function ShellWithData({ children, step, width, bare = false }: Props) {
  const id = useSearchParams().get("id") ?? "";
  const [contract, setContract] = useState<ContractOut | null>(null);
  const [me, setMe] = useState<UserOut | null>(null);

  const reload = useCallback(() => {
    if (!id) return;
    api<ContractOut>(`/contracts/${id}`).then(setContract, () => {
      // 이름·상태를 못 불러와도 화면 본문은 자기 오류 처리를 한다
    });
  }, [id]);

  useEffect(reload, [reload]);
  useEffect(() => {
    if (bare) return;
    // 로그인하지 않았으면 api()가 로그인 화면으로 보낸다
    api<UserOut>("/auth/me").then(setMe, () => {});
  }, [bare]);

  const current = contract?.id === id ? contract : null;

  return (
    <ContractContext.Provider value={{ contract: current, reload }}>
      <Frame
        width={width}
        header={<TopBar contract={current} me={me} bare={bare} />}
        body={
          <>
            {step && id && <StepNav contractId={id} step={step} status={current?.status ?? null} />}
            {children}
          </>
        }
      />
    </ContractContext.Provider>
  );
}

function TopBar({ contract, me, bare }: { contract: ContractOut | null; me: UserOut | null; bare: boolean }) {
  const router = useRouter();

  async function logout() {
    try {
      await api("/auth/logout", { method: "POST" });
    } finally {
      setToken(null);
      router.push("/login");
    }
  }

  return (
    <header className="border-b border-line bg-surface">
      <div className="mx-auto flex min-h-14 max-w-5xl items-center gap-3 px-4 sm:px-6">
        <Link href="/" className="-ml-2 flex min-h-11 items-center rounded-control px-2 text-card font-bold text-brand">
          오픈북
        </Link>
        <p className="min-w-0 flex-1 truncate text-center text-small text-muted" title={contract?.title}>
          {contract?.title}
        </p>
        {!bare && me && (
          <div className="flex shrink-0 items-center gap-2 text-small">
            {me.auth_disabled ? (
              <span className="rounded-control border border-line px-2 py-1 text-muted">로컬 모드</span>
            ) : (
              <>
                <span className="hidden max-w-48 truncate text-muted sm:inline">{me.email}</span>
                <button type="button" className={buttonClass("secondary")} onClick={logout}>
                  로그아웃
                </button>
              </>
            )}
          </div>
        )}
      </div>
    </header>
  );
}
