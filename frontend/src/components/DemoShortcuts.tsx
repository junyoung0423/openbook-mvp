import Link from "next/link";
import type { ContractOut } from "../lib/api";
import { Card, CardHeader } from "./Card";

// 시드 스크립트(backend/scripts/seed_demo.py)가 넣는 '데모1·2·3 …' 확정 계약서는 바로 결과를 볼 수 있게 따로 보여 준다.
// 같은 번호가 여러 개면 맨 앞(가장 최근)만 쓰고 번호 순으로 보여 준다. 번호는 한 자리 숫자 글자라 글자 비교로 정렬한다.
const demoNo = (c: ContractOut) => /^데모([0-9])/.exec(c.title)?.[1];

export function demoContracts(contracts: ContractOut[]): ContractOut[] {
  return contracts
    .filter((c) => demoNo(c) && c.status.replace(/\s/g, "") === "확정")
    .filter((c, i, all) => all.findIndex((o) => demoNo(o) === demoNo(c)) === i)
    .sort((a, b) => (demoNo(a) ?? "").localeCompare(demoNo(b) ?? ""))
    .slice(0, 3);
}

export function DemoShortcuts({ contracts }: { contracts: ContractOut[] }) {
  const demos = demoContracts(contracts);
  if (demos.length === 0) return null;
  return (
    <Card aria-labelledby="demo-shortcuts">
      <CardHeader as="h2" title={<span id="demo-shortcuts">데모로 둘러보기</span>} description="가상 계약서·정산서로 미리 만들어 둔 결과입니다." />
      <div className="grid gap-3 sm:grid-cols-3">
        {demos.map((c) => (
          <Link
            key={c.id}
            href={`/results?id=${c.id}`}
            className="flex min-h-11 flex-col gap-1 rounded-tile border border-line bg-card px-4 py-3 hover:bg-surface"
          >
            <span className="font-semibold">{c.title}</span>
            <span className="text-small font-semibold text-accent">대조 결과 보기 →</span>
          </Link>
        ))}
      </div>
    </Card>
  );
}
