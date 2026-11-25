"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import {
  api,
  errorText,
  field,
  primary,
  secondary,
  setToken,
  type ContractOut,
  type UserOut,
} from "../lib/api";

const FILE_TYPES = /\.(pdf|docx?|hwp|hwpx|jpe?g|png|webp|tiff?|bmp|heic)$/i;
// 백엔드 MAX_FILE_BYTES와 같게. Vercel 함수가 요청 본문을 4.5MB까지만 받는다
const MAX_FILE_BYTES = 4 * 1024 * 1024;
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

export default function Home() {
  const router = useRouter();
  const [mode, setMode] = useState<"file" | "text">("file");
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [contracts, setContracts] = useState<ContractOut[]>([]);

  const tooLarge = (file?.size ?? 0) > MAX_FILE_BYTES;
  const validFile = Boolean(file?.size) && !tooLarge && FILE_TYPES.test(file?.name ?? "");
  const canSubmit =
    consent && !busy && (mode === "file" ? validFile : Boolean(text.trim() && title.trim()));

  const [me, setMe] = useState<UserOut | null>(null);

  async function refresh() {
    try {
      setMe(await api<UserOut>("/auth/me")); // 로그인하지 않았으면 로그인 화면으로 이동
      setContracts(await api<ContractOut[]>("/contracts"));
    } catch (e) {
      setMessage(errorText(e));
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

  useEffect(() => {
    // 처음 열 때 내 계약서 목록을 불러온다
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refresh();
  }, []);

  async function waitUntilProcessed(id: string): Promise<ContractOut> {
    for (let i = 0; i < 90; i++) {
      const c = await api<ContractOut>(`/contracts/${id}`);
      if (c.status !== "처리중") return c;
      await sleep(2000);
    }
    throw new Error("timeout");
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canSubmit) return;
    setBusy(true);
    setMessage("계약서를 읽는 중입니다. 1~2분 걸릴 수 있습니다.");
    try {
      let created: ContractOut;
      if (mode === "file" && file) {
        const form = new FormData();
        form.append("file", file);
        if (title.trim()) form.append("title", title.trim());
        created = await api<ContractOut>("/contracts", { method: "POST", body: form });
      } else {
        created = await api<ContractOut>("/contracts/text", {
          method: "POST",
          body: JSON.stringify({ title: title.trim(), text }),
        });
      }
      const done = await waitUntilProcessed(created.id);
      if (done.status === "처리 실패") {
        setMessage(
          "계약서를 읽지 못했습니다. 다른 파일로 올리거나, 본문을 붙여넣어 다시 시도해 주세요.",
        );
      } else {
        router.push(`/terms?id=${done.id}`);
        return;
      }
    } catch (e) {
      setMessage(e instanceof Error && e.message === "timeout" ? "처리가 늦어지고 있습니다. 목록에서 상태를 확인해 주세요." : errorText(e));
    } finally {
      setBusy(false);
      void refresh();
    }
  }

  async function remove(c: ContractOut) {
    if (!window.confirm(`'${c.title}' 계약서와 정산 기록을 모두 삭제할까요? 되돌릴 수 없습니다.`)) return;
    try {
      await api(`/contracts/${c.id}`, { method: "DELETE" });
      await refresh();
    } catch (e) {
      setMessage(errorText(e));
    }
  }

  return (
    <main className="min-h-screen bg-stone-100 px-5 py-10 text-stone-900">
      <div className="mx-auto max-w-2xl space-y-5">
        <header className="flex flex-wrap items-center justify-between gap-2">
          <span className="font-bold text-teal-900">오픈북</span>
          {me && (
            <span className="flex items-center gap-3 text-sm">
              {me.auth_disabled ? (
                <span className="rounded border border-stone-300 px-2 py-1">로컬 모드 · 로그인 꺼짐</span>
              ) : (
                <>
                  {me.email}
                  <button type="button" className={secondary} onClick={logout}>
                    로그아웃
                  </button>
                </>
              )}
            </span>
          )}
        </header>

        <form onSubmit={submit} className="space-y-5 rounded-2xl bg-white p-6">
          <h1 className="text-2xl font-bold">계약서 올리기</h1>

          <fieldset className="flex flex-wrap gap-4">
            <legend className="mb-2 font-medium">입력 방식</legend>
            <label>
              <input type="radio" name="mode" checked={mode === "file"} onChange={() => setMode("file")} /> 파일
            </label>
            <label>
              <input type="radio" name="mode" checked={mode === "text"} onChange={() => setMode("text")} /> 본문
              붙여넣기
            </label>
          </fieldset>

          <label className="block">
            계약서 이름 {mode === "file" && <span className="text-sm text-stone-600">(비우면 파일 이름)</span>}
            <input className={field} value={title} maxLength={255} onChange={(e) => setTitle(e.target.value)} />
          </label>

          {mode === "file" ? (
            <label className="block">
              계약서 파일 <span className="text-sm text-stone-600">PDF, DOCX, HWP, 사진·스캔 이미지 (4MB까지)</span>
              <input
                type="file"
                className={field}
                accept=".pdf,.doc,.docx,.hwp,.hwpx,.jpg,.jpeg,.png,.webp,.tif,.tiff,.bmp,.heic"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
              {file && !validFile && (
                <span role="alert" className="mt-2 block text-sm">
                  {tooLarge
                    ? "파일은 4MB까지 올릴 수 있습니다. 큰 파일은 '본문 붙여넣기'로 올려 주세요."
                    : "지원하는 형식의 비어 있지 않은 파일을 선택해 주세요."}
                </span>
              )}
            </label>
          ) : (
            <label className="block">
              계약서 본문
              <textarea className={field} rows={8} value={text} onChange={(e) => setText(e.target.value)} />
            </label>
          )}

          <div className="space-y-3 rounded-lg bg-stone-100 p-4 text-sm">
            <p id="privacy-notice">
              계약서에는 실명·연락처·계좌 등이 있을 수 있습니다. 계약서 내용은 Upstage Document Parse(문서
              읽기)와 Solar Pro 4(분석)로 전송됩니다. 원본 파일은 오픈북 서버에 보관하지 않습니다.
            </p>
            <label className="flex items-start gap-2">
              <input
                className="mt-1"
                type="checkbox"
                aria-describedby="privacy-notice"
                checked={consent}
                onChange={(e) => setConsent(e.target.checked)}
              />
              개인정보 안내를 확인했으며 외부 서비스 전송에 동의합니다.
            </label>
          </div>

          <button className={primary} disabled={!canSubmit} type="submit">
            {busy ? "처리 중…" : "올리기"}
          </button>
          {message && <p role="status">{message}</p>}
        </form>

        <section className="space-y-3 rounded-2xl bg-white p-6">
          <h2 className="text-lg font-semibold">내 계약서</h2>
          {contracts.length === 0 && <p className="text-stone-600">아직 올린 계약서가 없습니다.</p>}
          {contracts.map((c) => (
            <div key={c.id} className="flex flex-wrap items-center justify-between gap-2 border-t border-stone-200 pt-3">
              <div>
                <p className="font-medium">{c.title}</p>
                <p className="text-sm text-stone-600">{c.status}</p>
              </div>
              <div className="flex gap-2">
                {c.status !== "처리중" && c.status !== "처리 실패" && (
                  <>
                    <Link className={secondary} href={`/terms?id=${c.id}`}>조건</Link>
                    <Link className={secondary} href={`/statements?id=${c.id}`}>정산서</Link>
                    <Link className={secondary} href={`/results?id=${c.id}`}>대조 결과</Link>
                    <Link className={secondary} href={`/qa?id=${c.id}`}>질문하기</Link>
                  </>
                )}
                <button type="button" className={secondary} onClick={() => remove(c)}>
                  삭제
                </button>
              </div>
            </div>
          ))}
        </section>
      </div>
    </main>
  );
}
