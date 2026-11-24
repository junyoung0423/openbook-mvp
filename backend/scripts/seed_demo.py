"""데모 1–3을 로컬 API에 한 번에 넣는다 (심사 데모 예비용).

화면으로 올리는 흐름이 느리거나 AI 호출이 실패할 때를 대비해 미리 만들어 둔다.
계약서 본문 올리기 → 처리 끝날 때까지 기다림 → 필수 조건 5개 확정 → 정산서 붙여넣기 읽기·저장.

사용 (api 서버가 OPENBOOK_AUTH_DISABLED=1 로컬 모드로 켜져 있어야 한다):
    python backend/scripts/seed_demo.py                # 데모 1–3 전부
    python backend/scripts/seed_demo.py --only 1 2     # 고른 데모만
    python backend/scripts/seed_demo.py --skip-last 1  # 데모 1의 마지막 달은 화면에서 넣도록 남김

조건 값은 data/samples/demo/README.md의 '조건 화면에서 확인할 값'과 같다. 금액은 모두 가상이다.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

DEMO = Path(__file__).resolve().parents[2] / "data" / "samples" / "demo"
APP_FEE = [{"name": "앱마켓 수수료", "rate": "0.3"}]
TERMS = {
    1: {
        "mg_amount": "3000000",
        "mg_recoup": "from_rs",
        "rs_rate": "0.65",
        "revenue_base": "net",
        "deductions": APP_FEE,
    },
    2: {
        "mg_amount": "1000000",
        "mg_recoup": "separate",
        "rs_rate": "0.5",
        "revenue_base": "gross",
        "deductions": [
            {"name": "결제 수수료", "rate": "0.05"},
            {"name": "서버 운영비", "amount": "50000"},
        ],
    },
    3: {
        "mg_amount": "2000000",
        "mg_recoup": "from_rs",
        "rs_rate": [
            {"from_amount": "0", "to_amount": "10000000", "rate": "0.5"},
            {"from_amount": "10000000", "to_amount": None, "rate": "0.6"},
        ],
        "revenue_base": "net",
        "deductions": APP_FEE,
    },
}
TITLES = {1: "데모1 새벽 정원", 2: "데모2 바다 끝 우체국", 3: "데모3 여름의 끝에서"}
STATEMENT_FIELDS = (
    "period_start",
    "period_end",
    "gross",
    "net_revenue",
    "reported_settlement",
    "reported_withholding",
    "reported_payout",
)


def call(base: str, method: str, path: str, body: object | None = None) -> object:
    req = urllib.request.Request(
        base + path,
        method=method,
        data=None if body is None else json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            text = r.read()
            return json.loads(text) if text else None
    except urllib.error.HTTPError as e:
        raise SystemExit(f"{method} {path} 실패: HTTP {e.code}") from None


def blocks(n: int) -> list[str]:
    text = (DEMO / f"demo{n}_statements.txt").read_text(encoding="utf-8")
    return [b.strip() for b in re.split(r"^=== .* ===$", text, flags=re.MULTILINE)[1:]]


def seed(base: str, n: int, skip_last: int) -> str:
    body = {
        "title": TITLES[n],
        "text": (DEMO / f"demo{n}_contract.txt").read_text(encoding="utf-8"),
    }
    cid = call(base, "POST", "/contracts/text", body)["id"]
    for _ in range(180):  # 처리중에는 조건을 확정할 수 없다 (409)
        status = call(base, "GET", f"/contracts/{cid}")["status"]
        if status != "처리중":
            break
        time.sleep(1)
    if status == "처리 실패":
        raise SystemExit(f"데모 {n}: 계약서 처리 실패 (Upstage 키·네트워크 확인)")
    terms = [{"key": k, "value": v, "confirmed": True} for k, v in TERMS[n].items()]
    call(base, "PUT", f"/contracts/{cid}/terms", {"terms": terms})
    todo = blocks(n)
    if skip_last:
        todo = todo[:-skip_last]
    for b in todo:
        d = call(base, "POST", f"/contracts/{cid}/statements/paste", {"text": b})
        st = {k: d.get(k) for k in STATEMENT_FIELDS}
        st["deductions"] = d["deductions"]
        call(base, "POST", f"/contracts/{cid}/statements", st)
    return cid


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--base", default="http://localhost:8000")
    p.add_argument("--only", type=int, nargs="*", default=[1, 2, 3])
    p.add_argument("--skip-last", type=int, default=0, help="데모 1의 마지막 N달은 넣지 않음")
    args = p.parse_args()
    for n in args.only:
        cid = seed(args.base, n, args.skip_last if n == 1 else 0)
        print(f"데모 {n}: http://localhost:3000/results?id={cid}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
