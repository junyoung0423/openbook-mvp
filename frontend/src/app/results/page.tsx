import Link from "next/link";

export default function ResultsPage() {
  return (
    <main className="min-h-screen bg-stone-100 px-4 py-10 text-stone-900">
      <div className="mx-auto max-w-5xl space-y-6">
        <header>
          <Link href="/" className="font-bold text-teal-900">
            오픈북
          </Link>
          <h1 className="mt-6 text-3xl font-bold">정산 대조 결과</h1>
          <p className="mt-3 text-stone-600">
            이 결과는 사용자가 확정한 조건에 대한 계산입니다.
          </p>
        </header>

        <section className="rounded-2xl bg-white p-6">
          <h2 className="text-xl font-bold">결과 준비 중</h2>
          <p className="mt-3">
            계산·대조 API가 연결되면 서버에서 받은 금액과 근거를 표시합니다.
            현재는 계산 결과가 없습니다.
          </p>
        </section>

        <section
          aria-label="대조 금액"
          className="grid gap-4 sm:grid-cols-3"
        >
          {["계약서 기준 금액", "정산서 금액", "차이"].map((label) => (
            <div key={label} className="rounded-2xl bg-white p-6">
              <h2 className="font-medium">{label}</h2>
              <p className="mt-4 text-3xl font-bold" aria-label="결과 없음">
                —
              </p>
            </div>
          ))}
        </section>

        <section className="rounded-2xl bg-white p-6">
          <h2 className="text-xl font-bold">계산 내역과 근거 조항</h2>
          <p className="mt-3 text-stone-600">
            결과를 받으면 단계별 계산 내역과 사용한 조건, 근거 조항 원문을
            여기에 표시합니다.
          </p>
        </section>

        <section className="rounded-2xl bg-white p-6">
          <h2 className="text-xl font-bold">플랫폼에 확인할 질문</h2>
          <p className="mt-3 text-stone-600">
            아직 표시할 질문이 없습니다. 대조 응답을 받으면 표시합니다.
          </p>
        </section>

        <section className="rounded-2xl bg-white p-6">
          <h2 className="text-xl font-bold">결과 안내</h2>
          <p className="mt-3">기준일: 결과 응답 대기 중</p>
          <p className="mt-3 text-stone-600">
            계약서 문구의 해석이나 적용 여부에 대한 판단이 필요하면
            관련 전문가와 상담해 주세요.
          </p>
        </section>

        <Link
          href="/statements"
          className="inline-block rounded-lg border border-stone-300 bg-white px-4 py-2"
        >
          정산서 입력으로 돌아가기
        </Link>
      </div>
    </main>
  );
}