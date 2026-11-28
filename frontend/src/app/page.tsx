"use client";

import { FileText, Upload } from "lucide-react";
import { useRouter } from "next/navigation";
import { useRef, useState, type FormEvent } from "react";
import { Card } from "../components/Card";
import { DemoShortcuts } from "../components/DemoShortcuts";
import { useContracts } from "../components/ShellContext";
import { Spinner } from "../components/Spinner";
import { api, ApiError, errorText, type ContractOut } from "../lib/api";
import { buttonClass, fieldClass } from "../lib/ui";

const FILE_TYPES = /\.(pdf|docx?|hwp|hwpx|jpe?g|png|webp|tiff?|bmp|heic)$/i;
// 백엔드 MAX_FILE_BYTES와 같게. Vercel 함수가 요청 본문을 4.5MB까지만 받는다
const MAX_FILE_BYTES = 4 * 1024 * 1024;
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

// 파일 크기 표시 (금액이 아니라 파일 용량이다)
const fileSize = (bytes: number) => (bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))}KB` : `${(bytes / (1024 * 1024)).toFixed(1)}MB`);

const STEPS = [
  ["STEP 1", "계약서 올리기", "MG·RS 조건을 원문과 함께 찾아요"],
  ["STEP 2", "조건 확인", "확인한 값만 계산에 써요"],
  ["STEP 3", "정산서 붙여넣기", "계약서 기준 금액과 나란히 봐요"],
] as const;

export default function Home() {
  const router = useRouter();
  // 사이드바와 같은 내 계약서 목록. 업로드가 끝나면 reloadContracts()로 맞춘다
  const { contracts, reloadContracts } = useContracts();
  const [mode, setMode] = useState<"file" | "text">("file");
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [uploadFailure, setUploadFailure] = useState<"temporary" | "unreadable" | null>(null);
  const [pendingContractId, setPendingContractId] = useState<string | null>(null);
  const [fileInputKey, setFileInputKey] = useState(0);
  const [dragging, setDragging] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  const tooLarge = (file?.size ?? 0) > MAX_FILE_BYTES;
  const validFile = Boolean(file?.size) && !tooLarge && FILE_TYPES.test(file?.name ?? "");
  const canSubmit = consent && !busy && (mode === "file" ? validFile : Boolean(text.trim() && title.trim()));

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
        (e instanceof Error && e.message === "timeout") || (e instanceof ApiError && (e.code === "NETWORK" || e.status === 429 || e.status >= 500));

      setUploadFailure(temporary ? "temporary" : null);
      setMessage(e instanceof Error && e.message === "timeout" ? "처리가 늦어지고 있습니다. 다시 시도하면 처리 상태를 확인합니다." : errorText(e));
    } finally {
      setBusy(false);
      void reloadContracts().catch(() => {});
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-[680px] flex-col gap-[22px] md:pt-8">
      <div className="flex flex-col gap-2.5 text-center">
        <h1 className="text-[26px] font-extrabold tracking-[-0.035em] md:text-page">계약서를 올려 시작하세요</h1>
        <p className="text-base leading-relaxed text-ink-2">
          계약서의 MG·RS 조건으로 정산서를 다시 계산해,
          <br />
          정산서 금액과 나란히 보여 드립니다.
        </p>
      </div>

      {!busy && <DemoShortcuts contracts={contracts ?? []} />}

      {busy ? (
        <Card role="status" className="flex flex-col gap-[18px] !rounded-[12px] !p-6 md:!p-[30px]">
          <div className="flex flex-col gap-1.5">
            <h2 className="text-title font-[750]">계약서를 읽는 중입니다</h2>
            <p className="text-sm text-ink-2">보통 20초 안팎, 길면 1~2분 걸립니다. 끝나면 조건 확인 화면으로 넘어가요.</p>
          </div>
          <div className="flex items-center gap-3 rounded-tile border border-accent-line bg-accent-soft px-4 py-3.5 text-[15px] font-bold text-accent">
            <Spinner />
            계약서를 읽고 조건을 찾는 중
          </div>
          {/* 서버가 단계별 상태를 주지 않으므로 가짜 진행률은 쓰지 않고, 하는 일만 설명한다 */}
          <div className="flex flex-col gap-1.5">
            <p className="text-small font-bold text-ink-2">이 동안 하는 일</p>
            <ol className="flex list-decimal flex-col gap-1 pl-5 text-sm leading-relaxed text-ink-2">
              <li>문서 읽기 (Upstage Document Parse)</li>
              <li>조항 나누기</li>
              <li>MG·RS 조건과 근거 원문 찾기 (Solar Pro 4)</li>
            </ol>
            <p className="text-fine text-muted">단계별 진행률은 서버가 알려 주지 않아서 표시하지 않습니다.</p>
          </div>
        </Card>
      ) : (
        <form onSubmit={submit}>
          <Card className="flex flex-col gap-4 !rounded-[12px] !p-5 md:!p-[26px]">
            <div role="tablist" aria-label="입력 방식" className="flex self-start rounded-tabbar bg-line-soft p-[3px] text-sm">
              {(
                [
                  ["file", "파일 올리기"],
                  ["text", "본문 붙여넣기"],
                ] as const
              ).map(([m, label]) => (
                <button
                  key={m}
                  type="button"
                  role="tab"
                  aria-selected={mode === m}
                  onClick={() => {
                    setMode(m);
                    resetPending();
                  }}
                  className={`min-h-[38px] rounded-tab px-4 ${mode === m ? "bg-card font-bold text-ink shadow-tab" : "font-semibold text-ink-2"}`}
                >
                  {label}
                </button>
              ))}
            </div>

            {mode === "file" ? (
              <>
                <label
                  className={`flex min-w-0 cursor-pointer flex-col items-center gap-3 rounded-card border-[1.5px] border-dashed border-[#b9c1d9] px-5 py-[34px] text-center has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-accent ${
                    dragging ? "bg-accent-soft" : "bg-[#f9fafd]"
                  }`}
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
                  {/* 브라우저 기본 파일 칸(영어)은 숨기고, 선택한 파일 이름은 아래 줄에 직접 보여 준다 (끌어다 놓아도 같은 표시) */}
                  <input
                    ref={fileInput}
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
                  <span aria-hidden className="grid size-[52px] place-items-center rounded-tile bg-accent-soft text-accent">
                    <Upload size={24} strokeWidth={2} />
                  </span>
                  <span className="text-base font-bold">계약서 파일을 여기에 끌어다 놓으세요</span>
                  <span className="text-small text-muted">PDF · DOCX · HWP · 사진·스캔 이미지 · 4MB까지</span>
                  <span className={`${buttonClass("dark")} mt-1 !min-h-11 !px-5 !text-sm`}>파일 선택</span>
                </label>
                {file && (
                  <div className="flex items-center gap-3 rounded-tile border border-line px-3.5 py-3">
                    <span aria-hidden className="grid size-9 shrink-0 place-items-center rounded-tag bg-surface text-ink-2">
                      <FileText size={18} />
                    </span>
                    <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                      <span className="break-all text-sm font-[650]">{file.name}</span>
                      <span className="num text-fine text-muted">{fileSize(file.size)} · 선택한 파일</span>
                    </span>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => fileInput.current?.click()}
                      className="min-h-11 shrink-0 rounded-btn px-3 text-[13px] font-[650] text-accent hover:bg-accent-soft"
                    >
                      다른 파일
                    </button>
                  </div>
                )}
                {file && !validFile && (
                  <p role="alert" className="text-sm text-error">
                    {tooLarge
                      ? "파일은 4MB까지 올릴 수 있습니다. 큰 파일은 '본문 붙여넣기'로 올려 주세요."
                      : "지원하는 형식의 비어 있지 않은 파일을 선택해 주세요."}
                  </p>
                )}
              </>
            ) : (
              <label className="block text-small font-semibold">
                계약서 본문
                <textarea
                  className={`${fieldClass} font-normal`}
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

            <label className="block min-w-0 text-small font-semibold">
              계약서 이름 {mode === "file" && <span className="font-medium text-muted">비우면 파일 이름</span>}
              <input
                className={`${fieldClass} min-w-0 font-normal`}
                value={title}
                maxLength={255}
                placeholder="예: 새벽 정원 연재 계약"
                onChange={(e) => {
                  setTitle(e.target.value);
                  resetPending();
                }}
              />
            </label>

            <div className="flex flex-col gap-3 rounded-tile bg-quote px-[18px] py-4">
              <p id="privacy-notice" className="text-small leading-[1.65] text-[#3a3f52]">
                계약서에는 실명·연락처·계좌 등이 있을 수 있습니다. 계약서 내용은 Upstage Document Parse(문서 읽기)와 Solar Pro 4(분석)로 전송됩니다. 원본 파일은 오픈북
                서버에 보관하지 않습니다.
              </p>
              <label className="flex min-h-11 cursor-pointer items-center gap-2.5 text-sm font-semibold">
                <input
                  className="size-[18px] shrink-0 accent-accent"
                  type="checkbox"
                  aria-describedby="privacy-notice"
                  checked={consent}
                  onChange={(e) => setConsent(e.target.checked)}
                />
                개인정보 안내를 확인했으며 외부 서비스 전송에 동의합니다.
              </label>
            </div>

            <button className={`${buttonClass("primary")} !min-h-[52px] !text-base`} disabled={!canSubmit} type="submit">
              올리고 조건 찾기
            </button>
            {message && (
              <p role="status" className="rounded-tile bg-quote px-3.5 py-2.5 text-sm text-ink-2">
                {message}
              </p>
            )}
            {uploadFailure && (
              <div className="flex flex-wrap gap-2">
                {uploadFailure === "temporary" && (
                  <button type="submit" className={buttonClass("secondary")} disabled={!canSubmit}>
                    다시 시도
                  </button>
                )}

                {uploadFailure === "unreadable" && (
                  <>
                    <button
                      type="button"
                      className={buttonClass("secondary")}
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
                      className={buttonClass("secondary")}
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
          </Card>
        </form>
      )}

      <ol className="grid gap-2.5 sm:grid-cols-3">
        {STEPS.map(([step, name, desc]) => (
          <li key={step} className="flex flex-col gap-1.5 rounded-tile bg-card px-[18px] py-4">
            <span className="text-fine font-extrabold tracking-[0.08em] text-accent">{step}</span>
            <span className="text-[15px] font-bold">{name}</span>
            <span className="text-small leading-normal text-muted">{desc}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}
