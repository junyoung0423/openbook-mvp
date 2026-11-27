"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import Shell from "../components/Shell";
import {
  api,
  ApiError,
  errorText,
  field,
  primary,
  secondary,
  setToken,
  statusChip,
  type ContractOut,
  type UserOut,
} from "../lib/api";

const FILE_TYPES = /\.(pdf|docx?|hwp|hwpx|jpe?g|png|webp|tiff?|bmp|heic)$/i;
// 백엔드 MAX_FILE_BYTES와 같게. Vercel 함수가 요청 본문을 4.5MB까지만 받는다
const MAX_FILE_BYTES = 4 * 1024 * 1024;
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

const HOW_IT_WORKS = [
  ["1", "계약서 올리기", "조건과 근거 조항 찾기"],
  ["2", "정산서 붙여넣기", "표에서 금액 자동 채움"],
  ["3", "대조 결과", "차이와 확인 질문"],
] as const;

const actionLink = "rounded-lg px-2 py-1 font-medium text-teal-800 transition hover:bg-teal-50";

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
  const [uploadFailure, setUploadFailure] =
    useState<"temporary" | "unreadable" | null>(null);
  const [pendingContractId, setPendingContractId] = useState<string | null>(null);
  const [fileInputKey, setFileInputKey] = useState(0);
  const [dragging, setDragging] = useState(false);

  const tooLarge = (file?.size ?? 0) > MAX_FILE_BYTES;
  const validFile = Boolean(file?.size) && !tooLarge && FILE_TYPES.test(file?.name ?? "");
  const canSubmit =
    consent && !busy && (mode === "file" ? validFile : Boolean(text.trim() && title.trim()));

  const [me, setMe] = useState<UserOut | null>(null);

  // 입력이 바뀌면 앞서 만든 계약서로 다시 시도하지 않는다
  function resetPending() {
    setPendingContractId(null);
    setUploadFailure(null);
  }

  function pickFile(f: File | null) {
    setFile(f);
    setFileInputKey((key) => key + 1);
    resetPending();
    setMessage("");
  }

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
    setUploadFailure(null);
    setMessage("계약서를 읽는 중입니다. 1~2분 걸릴 수 있습니다.");
    try {
      let created: ContractOut;
      if (pendingContractId) {
        created = { id: pendingContractId } as ContractOut;
      } else if (mode === "file" && file) {
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
      setPendingContractId(created.id);
      const done = await waitUntilProcessed(created.id);
      if (done.status.replace(/\s/g, "") === "처리실패") {
        setPendingContractId(null);
        setUploadFailure("unreadable");
        setMessage("계약서를 읽지 못했습니다. 다른 파일을 선택하거나 본문을 붙여넣어 주세요.");
      } else {
        setPendingContractId(null);
        router.push(`/terms?id=${done.id}`);
        return;
      }
    } catch (e) {
      const temporary =
        (e instanceof Error && e.message === "timeout") ||
        (e instanceof ApiError && (e.code === "NETWORK" || e.status === 429 || e.status >= 500));

      setUploadFailure(temporary ? "temporary" : null);
      setMessage(
        e instanceof Error && e.message === "timeout"
          ? "처리가 늦어지고 있습니다. 다시 시도하면 처리 상태를 확인합니다."
          : errorText(e),
      );
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

  // 시드 스크립트가 넣는 '데모1·2·3 …' 확정 계약서는 바로 결과를 볼 수 있게 위에 따로 보여 준다
  // 같은 번호가 여러 번 있으면 맨 앞(가장 최근)만 쓰고, 번호 순으로 보여 준다
  const demoNo = (c: ContractOut) => /^데모(\d)/.exec(c.title)?.[1];
  const demos = contracts
    .filter((c) => demoNo(c) && c.status.replace(/\s/g, "") === "확정")
    .filter((c, i, all) => all.findIndex((o) => demoNo(o) === demoNo(c)) === i)
    .sort((a, b) => Number(demoNo(a)) - Number(demoNo(b)));

  return (
    <Shell
      step="upload"
      width="5xl"
      right={
        me && (
          <span className="flex items-center gap-2 text-sm text-stone-600">
            {me.auth_disabled ? (
              <span className="chip bg-stone-100 text-stone-600 ring-1 ring-stone-200">로컬 모드</span>
            ) : (
              <>
                <span className="hidden sm:inline">{me.email}</span>
                <button type="button" className={secondary} onClick={logout}>
                  로그아웃
                </button>
              </>
            )}
          </span>
        )
      }
    >
      <section className="grid gap-6 pt-2 md:grid-cols-[1.2fr_1fr] md:items-end">
        <div className="space-y-3">
          <p className="chip bg-teal-50 text-teal-800 ring-1 ring-teal-200">웹툰·웹소설 작가를 위한 정산 대조</p>
          <h1 className="text-3xl font-black leading-tight tracking-tight sm:text-4xl">
            정산서가 계약서대로
            <br />
            계산됐는지 <span className="text-teal-700">1원까지</span> 확인하세요
          </h1>
          <p className="max-w-xl text-stone-600">
            계약서를 올리면 AI가 정산 조건을 원문 조항과 함께 찾아 주고, 확인한 조건으로 규칙 엔진이 정산서를
            다시 계산합니다. 맞지 않는 곳은 플랫폼에 보낼 질문으로 정리해 드립니다.
          </p>
        </div>
        <ol className="grid grid-cols-3 gap-2 text-center text-sm">
          {HOW_IT_WORKS.map(([n, t, d]) => (
            <li key={n} className="card space-y-1 px-2 py-4">
              <span className="mx-auto grid h-7 w-7 place-items-center rounded-full bg-teal-800 text-xs font-bold text-white">
                {n}
              </span>
              <p className="font-semibold">{t}</p>
              <p className="text-xs text-stone-500">{d}</p>
            </li>
          ))}
        </ol>
      </section>

      {demos.length > 0 && (
        <section className="card space-y-3 bg-gradient-to-br from-amber-50 to-white p-6">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h2 className="text-lg font-bold">데모로 둘러보기</h2>
            <p className="text-sm text-stone-500">가상 계약서·정산서로 미리 만들어 둔 결과입니다.</p>
          </div>
          <div className="grid gap-3 sm:grid-cols-3">
            {demos.slice(0, 3).map((c) => (
              <Link
                key={c.id}
                href={`/results?id=${c.id}`}
                className="group rounded-xl border border-amber-200 bg-white p-4 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md"
              >
                <p className="font-semibold group-hover:text-teal-800">{c.title}</p>
                <p className="mt-1 text-sm text-stone-500">대조 결과 보기 →</p>
              </Link>
            ))}
          </div>
        </section>
      )}

      <div className="grid gap-5 md:grid-cols-[1.2fr_1fr] md:items-start">
        <form onSubmit={submit} className="card space-y-5 p-6">
          <h2 className="text-xl font-bold">계약서 올리기</h2>

          <fieldset>
            <legend className="sr-only">입력 방식</legend>
            <div className="inline-flex rounded-xl bg-stone-100 p-1 text-sm">
              {(
                [
                  ["file", "파일 올리기"],
                  ["text", "본문 붙여넣기"],
                ] as const
              ).map(([m, label]) => (
                <label
                  key={m}
                  className={
                    "cursor-pointer rounded-lg px-4 py-1.5 font-medium transition has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-teal-700 " +
                    (mode === m ? "bg-white text-teal-800 shadow-sm" : "text-stone-500 hover:text-stone-800")
                  }
                >
                  <input
                    type="radio"
                    name="mode"
                    className="sr-only"
                    checked={mode === m}
                    onChange={() => {
                      setMode(m);
                      resetPending();
                    }}
                  />
                  {label}
                </label>
              ))}
            </div>
          </fieldset>

          <label className="block text-sm font-medium">
            계약서 이름 {mode === "file" && <span className="font-normal text-stone-500">(비우면 파일 이름)</span>}
            <input
              className={field + " font-normal"}
              value={title}
              maxLength={255}
              onChange={(e) => {
                setTitle(e.target.value);
                resetPending();
              }}
            />
          </label>

          {mode === "file" ? (
            <label
              className={
                "block cursor-pointer rounded-xl border-2 border-dashed p-6 text-center transition has-[:focus-visible]:border-teal-600 " +
                (dragging ? "border-teal-600 bg-teal-50" : "border-stone-300 bg-stone-50/60 hover:border-teal-500")
              }
              onDragOver={(event) => {
                event.preventDefault();
                if (!busy) {
                  event.dataTransfer.dropEffect = "copy";
                  setDragging(true);
                }
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={(event) => {
                event.preventDefault();
                setDragging(false);
                if (busy) return;
                const files = event.dataTransfer.files;
                if (files.length !== 1) {
                  setMessage("계약서 파일을 한 개씩 놓아 주세요.");
                  return;
                }
                pickFile(files[0]);
              }}
            >
              {/* 실제 파일 칸은 숨기고, 선택한 파일 이름은 아래에 직접 보여 준다 (끌어다 놓아도 같은 표시) */}
              <input
                type="file"
                key={fileInputKey}
                className="sr-only"
                accept=".pdf,.doc,.docx,.hwp,.hwpx,.jpg,.jpeg,.png,.webp,.tif,.tiff,.bmp,.heic"
                onChange={(event) => {
                  setFile(event.target.files?.[0] ?? null);
                  resetPending();
                  setMessage("");
                }}
              />
              <span
                aria-hidden
                className="mx-auto mb-2 grid h-11 w-11 place-items-center rounded-full bg-white text-xl text-teal-700 shadow-sm"
              >
                ↑
              </span>
              <span className="block font-semibold">파일을 끌어다 놓거나 눌러서 선택</span>
              <span className="mt-1 block text-sm text-stone-500">PDF, DOCX, HWP, 사진·스캔 이미지 · 4MB까지</span>
              {file && (
                <span className="mt-3 inline-block max-w-full break-all rounded-lg bg-white px-3 py-1.5 text-sm font-medium shadow-sm ring-1 ring-stone-200">
                  선택한 파일: {file.name}
                </span>
              )}
              {file && !validFile && (
                <span role="alert" className="mt-2 block text-sm text-red-700">
                  {tooLarge
                    ? "파일은 4MB까지 올릴 수 있습니다. 큰 파일은 '본문 붙여넣기'로 올려 주세요."
                    : "지원하는 형식의 비어 있지 않은 파일을 선택해 주세요."}
                </span>
              )}
            </label>
          ) : (
            <label className="block text-sm font-medium">
              계약서 본문
              <textarea
                className={field + " font-normal"}
                rows={8}
                value={text}
                placeholder="계약서 내용을 그대로 붙여넣어 주세요."
                onChange={(e) => {
                  setText(e.target.value);
                  resetPending();
                }}
              />
            </label>
          )}

          <div className="space-y-3 rounded-xl bg-stone-50 p-4 text-sm text-stone-600 ring-1 ring-stone-200">
            <p id="privacy-notice">
              계약서에는 실명·연락처·계좌 등이 있을 수 있습니다. 계약서 내용은 Upstage Document Parse(문서
              읽기)와 Solar Pro 4(분석)로 전송됩니다. 원본 파일은 오픈북 서버에 보관하지 않습니다.
            </p>
            <label className="flex items-start gap-2 font-medium text-stone-800">
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

          <button className={primary + " w-full"} disabled={!canSubmit} type="submit">
            {busy && (
              <span aria-hidden className="h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white" />
            )}
            {busy ? "계약서 읽는 중…" : "올리고 조건 찾기"}
          </button>
          {message && (
            <p role="status" className="rounded-lg bg-stone-50 px-3 py-2 text-sm text-stone-700">
              {message}
            </p>
          )}
          {uploadFailure && (
            <div className="flex flex-wrap gap-2">
              {uploadFailure === "temporary" && (
                <button type="submit" className={secondary} disabled={!canSubmit}>
                  다시 시도
                </button>
              )}
              {uploadFailure === "unreadable" && (
                <>
                  <button
                    type="button"
                    className={secondary}
                    disabled={busy}
                    onClick={() => {
                      setMode("file");
                      pickFile(null);
                      setMessage("위 파일 칸에서 다른 파일을 선택해 주세요.");
                    }}
                  >
                    다른 파일 선택
                  </button>
                  <button
                    type="button"
                    className={secondary}
                    disabled={busy}
                    onClick={() => {
                      setMode("text");
                      resetPending();
                      setMessage("계약서 이름과 본문을 입력한 뒤 올려 주세요.");
                    }}
                  >
                    본문 붙여넣기
                  </button>
                </>
              )}
            </div>
          )}
        </form>

        <section className="card p-6">
          <div className="mb-3 flex items-baseline justify-between">
            <h2 className="text-xl font-bold">내 계약서</h2>
            <span className="text-sm text-stone-500">{contracts.length}건</span>
          </div>
          {contracts.length === 0 && (
            <p className="rounded-xl bg-stone-50 p-6 text-center text-sm text-stone-500">아직 올린 계약서가 없습니다.</p>
          )}
          <ul className="divide-y divide-stone-100">
            {contracts.map((c) => {
              const ready = c.status !== "처리중" && c.status !== "처리 실패";
              return (
                <li key={c.id} className="space-y-2 py-3">
                  <div className="flex items-start justify-between gap-2">
                    <p className="font-semibold leading-snug">{c.title}</p>
                    <span className={statusChip(c.status)}>{c.status}</span>
                  </div>
                  <div className="flex flex-wrap items-center gap-1 text-sm">
                    {ready && (
                      <>
                        <Link className={actionLink} href={`/terms?id=${c.id}`}>
                          조건
                        </Link>
                        <Link className={actionLink} href={`/statements?id=${c.id}`}>
                          정산서
                        </Link>
                        <Link className={actionLink} href={`/results?id=${c.id}`}>
                          대조 결과
                        </Link>
                        <Link className={actionLink} href={`/qa?id=${c.id}`}>
                          질문하기
                        </Link>
                      </>
                    )}
                    <button
                      type="button"
                      className="ml-auto rounded-lg px-2 py-1 text-stone-400 transition hover:bg-red-50 hover:text-red-700"
                      onClick={() => remove(c)}
                    >
                      삭제
                    </button>
                  </div>
                </li>
              );
            })}
          </ul>
        </section>
      </div>
    </Shell>
  );
}
