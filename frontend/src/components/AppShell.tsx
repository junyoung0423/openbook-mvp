"use client";

import { usePathname, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState, type ReactNode } from "react";
import { api, type ContractOut, type UserOut } from "../lib/api";
import { CONTRACT_PATHS, ContractHeader } from "./ContractHeader";
import { Sidebar } from "./Sidebar";
import { ContractContext, ContractsContext } from "./ShellContext";

// 화면(경로)마다 본문 폭. 화면을 새 시안으로 바꾸는 PR에서 그 화면의 값을 시안에 맞춘다
const PATH_WIDTH: Record<string, string> = { "/": "max-w-2xl", "/terms": "max-w-3xl", "/statements": "max-w-3xl" };

// 모든 화면을 감싸는 틀: 바깥 canvas 배경 → 앱 창 → 왼쪽 사이드바 + 오른쪽 본문. app/layout.tsx에서 한 번만 쓴다.
// 로그인 화면은 앱 창 없이 canvas 배경 가운데 카드만 둔다.
export function AppShell({ children }: { children: ReactNode }) {
  // useSearchParams는 Suspense 안에서만 쓸 수 있다. 읽기 전에는 사이드바 뼈대만 보인다
  return (
    <Suspense fallback={<Frame sidebar={<Sidebar loading />}>{null}</Frame>}>
      <ShellWithData>{children}</ShellWithData>
    </Suspense>
  );
}

function Frame({ sidebar, children, width = "" }: { sidebar: ReactNode; children: ReactNode; width?: string }) {
  return (
    <div className="min-h-screen bg-surface md:bg-canvas md:p-7">
      <div className="mx-auto flex min-h-screen max-w-[1360px] flex-col px-4 md:min-h-[calc(100vh-3.5rem)] md:flex-row md:gap-3 md:rounded-window md:bg-surface md:p-3 md:shadow-window">
        {sidebar}
        <main className="min-w-0 flex-1 pb-10 pt-4 md:px-6 md:pt-5">
          <div className={`mx-auto flex w-full flex-col gap-[18px] ${width}`}>{children}</div>
        </main>
      </div>
    </div>
  );
}

function ShellWithData({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const id = useSearchParams().get("id") ?? "";
  const [contract, setContract] = useState<ContractOut | null>(null);
  const [contracts, setContracts] = useState<ContractOut[] | null>(null);
  const [me, setMe] = useState<UserOut | null>(null);
  const bare = pathname === "/login";

  const reload = useCallback(() => {
    if (!id) return;
    api<ContractOut>(`/contracts/${id}`).then(setContract, () => {
      // 이름·상태를 못 불러와도 화면 본문은 자기 오류 처리를 한다
    });
  }, [id]);

  const reloadContracts = useCallback(async () => {
    setContracts(await api<ContractOut[]>("/contracts"));
  }, []);

  useEffect(reload, [reload]);
  useEffect(() => {
    if (bare) return;
    // 로그인하지 않았으면 api()가 로그인 화면으로 보낸다
    api<UserOut>("/auth/me").then(setMe, () => {});
    api<ContractOut[]>("/contracts").then(setContracts, () => {});
  }, [bare]);

  const current = contract?.id === id ? contract : null;

  if (bare)
    return (
      <div className="min-h-screen bg-canvas px-5 py-10">
        <div className="mx-auto max-w-md space-y-5">
          <p className="text-center text-[17px] font-extrabold tracking-[0.2em]">OPENBOOK</p>
          {children}
        </div>
      </div>
    );

  return (
    <ContractsContext.Provider value={{ contracts, reloadContracts }}>
      <ContractContext.Provider value={{ contract: current, reload }}>
        <Frame width={PATH_WIDTH[pathname] ?? ""} sidebar={<Sidebar currentId={id} me={me} />}>
          {id && CONTRACT_PATHS.includes(pathname) && <ContractHeader contractId={id} />}
          {children}
        </Frame>
      </ContractContext.Provider>
    </ContractsContext.Provider>
  );
}
