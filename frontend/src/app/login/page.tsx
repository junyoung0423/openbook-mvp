"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState, type FormEvent } from "react";
import { api, errorText, field, primary, setToken, type LoginOut } from "../../lib/api";

// 로그인 뒤 돌아갈 주소는 이 사이트 안의 경로만 받는다 (다른 사이트로 보내지 않음)
function safeNext(next: string | null) {
  return next && next.startsWith("/") && !next.startsWith("//") ? next : "/";
}

function LoginInner() {
  const router = useRouter();
  const next = safeNext(useSearchParams().get("next"));
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (mode === "signup" && password.length < 8) return setMessage("비밀번호는 8자 이상으로 정해 주세요.");
    setBusy(true);
    setMessage("");
    try {
      const res = await api<LoginOut>(`/auth/${mode}`, {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      setToken(res.token);
      router.push(next);
    } catch (e) {
      setMessage(errorText(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-5 rounded-2xl bg-white p-6">
      <h1 className="text-2xl font-bold">{mode === "login" ? "로그인" : "회원가입"}</h1>
      <label className="block">
        이메일
        <input
          className={field}
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
      </label>
      <label className="block">
        비밀번호 {mode === "signup" && <span className="text-sm text-stone-600">(8자 이상)</span>}
        <input
          className={field}
          type="password"
          autoComplete={mode === "login" ? "current-password" : "new-password"}
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
      </label>
      <button className={primary} disabled={busy} type="submit">
        {busy ? "확인 중…" : mode === "login" ? "로그인" : "가입하기"}
      </button>
      {message && <p role="alert">{message}</p>}
      <p className="text-sm">
        {mode === "login" ? "처음이신가요? " : "이미 가입하셨나요? "}
        <button
          type="button"
          className="underline"
          onClick={() => {
            setMode(mode === "login" ? "signup" : "login");
            setMessage("");
          }}
        >
          {mode === "login" ? "회원가입" : "로그인"}
        </button>
      </p>
    </form>
  );
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginInner />
    </Suspense>
  );
}
