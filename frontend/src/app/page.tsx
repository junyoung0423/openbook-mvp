"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { useContracts } from "../components/ShellContext";
import {
  api,
  ApiError,
  errorText,
  field,
  primary,
  secondary,
  type ContractOut,
} from "../lib/api";

const FILE_TYPES = /\.(pdf|docx?|hwp|hwpx|jpe?g|png|webp|tiff?|bmp|heic)$/i;
// 백엔드 MAX_FILE_BYTES와 같게. Vercel 함수가 요청 본문을 4.5MB까지만 받는다
const MAX_FILE_BYTES = 4 * 1024 * 1024;
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

export default function Home() {
  const router = useRouter();
  const { reloadContracts } = useContracts();
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

  const tooLarge = (file?.size ?? 0) > MAX_FILE_BYTES;
  const validFile = Boolean(file?.size) && !tooLarge && FILE_TYPES.test(file?.name ?? "");
  const canSubmit =
    consent && !busy && (mode === "file" ? validFile : Boolean(text.trim() && title.trim()));

  async function refresh() {
    try {
      setContracts(await api<ContractOut[]>("/contracts"));
    } catch (e) {
      setMessage(errorText(e));
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
        setMessage(
          "계약서를 읽지 못했습니다. 다른 파일을 선택하거나 본문을 붙여넣어 주세요.",
        );
      } else {
        setPendingContractId(null);
        router.push(`/terms?id=${done.id}`);
        return;
      }
    } catch (e) {
      const temporary =
        (e instanceof Error && e.message === "timeout") ||
        (e instanceof ApiError &&
          (e.code === "NETWORK" || e.status === 429 || e.status >= 500));

      setUploadFailure(temporary ? "temporary" : null);
      setMessage(
        e instanceof Error && e.message === "timeout"
          ? "처리가 늦어지고 있습니다. 다시 시도하면 처리 상태를 확인합니다."
          : errorText(e),
      );
    } finally {
      setBusy(false);
      void refresh();
      void reloadContracts().catch(() => {});
    }
  }

  async function remove(c: ContractOut) {
    if (!window.confirm(`'${c.title}' 계약서와 정산 기록을 모두 삭제할까요? 되돌릴 수 없습니다.`)) return;
    try {
      await api(`/contracts/${c.id}`, { method: "DELETE" });
      await refresh();
      void reloadContracts().catch(() => {});
    } catch (e) {
      setMessage(errorText(e));
    }
  }

  return (
    <>
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
            <label
              className="block rounded-lg border-2 border-dashed border-stone-300 p-4"
              onDragOver={(event) => {
                event.preventDefault();
                if (!busy) event.dataTransfer.dropEffect = "copy";
              }}
              onDrop={(event) => {
                event.preventDefault();
                if (busy) return;

                const files = event.dataTransfer.files;
                if (files.length !== 1) {
                  setMessage("계약서 파일을 한 개씩 놓아 주세요.");
                  return;
                }

                setFile(files[0]);
                setFileInputKey((key) => key + 1);
                setPendingContractId(null);
                setUploadFailure(null);
                setMessage("");
              }}
            >
              계약서 파일 <span className="text-sm text-stone-600">PDF, DOCX, HWP, 사진·스캔 이미지 (4MB까지)</span>
              <input
                type="file"
                key={fileInputKey}
                className={field}
                accept=".pdf,.doc,.docx,.hwp,.hwpx,.jpg,.jpeg,.png,.webp,.tif,.tiff,.bmp,.heic"
                onChange={(event) => {
                  setFile(event.target.files?.[0] ?? null);
                  setPendingContractId(null);
                  setUploadFailure(null);
                  setMessage("");
                }}
              />
              <span className="mt-2 block text-sm text-stone-600">
                이 영역에 파일 한 개를 끌어다 놓거나 파일 선택 버튼을 눌러 주세요.
              </span>

              {file && (
                <span className="mt-2 block break-all text-sm">
                  선택한 파일: {file.name}
                </span>
              )}
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
          {uploadFailure && (
            <div className="flex flex-wrap gap-2">
              {uploadFailure === "temporary" && (
                <button
                  type="submit"
                  className={secondary}
                  disabled={!canSubmit}
                >
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
                      setFile(null);
                      setFileInputKey((key) => key + 1);
                      setPendingContractId(null);
                      setUploadFailure(null);
                      setMessage("아래 파일 선택 칸에서 다른 파일을 선택해 주세요.");
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
                      setPendingContractId(null);
                      setUploadFailure(null);
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
    </>
  );
}
