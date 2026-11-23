"""업로드 → 조건 확정 → 정산서 → 대조 → 삭제 흐름 (가상 계약서, 가짜 LLM·파서)."""

import calendar
from typing import Annotated

import pytest
from fastapi import Header
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from openbook.api.deps import (
    api_error,
    current_user_id,
    get_db,
    get_llm,
    get_parser,
    get_session_factory,
)
from openbook.api.main import app
from openbook.db import (
    Base,
    Reconciliation,
    Statement,
    User,
    create_db_engine,
    make_session_factory,
)
from openbook.parsing import DocumentParseError, ParsedDocument

TEXT = """웹툰 연재 계약서 (가상)

제1조 (목적)
이 계약은 가상의 작품 연재에 관한 사항을 정한다.

제2조 (선급금)
갑은 을에게 선급금 1,000,000원을 지급하고, 을의 수익배분금에서 차감한다.

제3조 (수익배분)
을의 수익배분율은 순매출의 60%로 한다. 순매출은 총매출에서 앱마켓 수수료 30%를 뺀 금액이다.
"""


def header_user(x_user_id: Annotated[str | None, Header()] = None) -> str:
    """테스트 전용: 로그인 대신 X-User-Id 헤더로 사용자를 고른다 (로그인은 test_auth.py)."""
    if not x_user_id:
        raise api_error(401, "UNAUTHENTICATED", "로그인이 필요합니다.")
    return x_user_id


class FakeLLM:
    def complete(self, system, user):
        return "{}"  # 조건을 하나도 못 찾은 경우 → 사용자가 직접 입력


class FakeParser:
    def __init__(self, fail=False):
        self.fail = fail

    def parse_file(self, filename, content, mime_type=None):
        if self.fail:
            raise DocumentParseError("Document Parse 호출에 실패했습니다: HTTP 500")
        return ParsedDocument(text=content.decode("utf-8"))


@pytest.fixture
def env(tmp_path):
    engine = create_db_engine(f"sqlite:///{tmp_path / 'flow.db'}")
    Base.metadata.create_all(engine)
    sessions = make_session_factory(engine)
    with sessions.begin() as s:
        s.add_all([User(id="u1", email="u1@example.test"), User(id="u2", email="u2@example.test")])
    parser = FakeParser()

    def _db():
        with sessions() as s:
            yield s

    app.dependency_overrides.update(
        {
            get_db: _db,
            get_session_factory: lambda: sessions,
            get_llm: lambda: FakeLLM(),
            get_parser: lambda: parser,
            current_user_id: header_user,
        }
    )
    yield TestClient(app, headers={"X-User-Id": "u1"}), sessions, parser
    app.dependency_overrides.clear()
    engine.dispose()


CONFIRM = {
    "terms": [
        {"key": "mg_amount", "value": "1000000", "confirmed": True},
        {"key": "mg_recoup", "value": "from_rs", "confirmed": True},
        {"key": "rs_rate", "value": "0.6", "confirmed": True},
        {"key": "revenue_base", "value": "net", "confirmed": True},
        {
            "key": "deductions",
            "value": [{"name": "앱마켓 수수료", "rate": "0.3"}],
            "confirmed": True,
        },
    ]
}


def _statement(month, gross, payout, deductions=()):
    return {
        "period_start": f"2026-{month:02d}-01",
        "period_end": f"2026-{month:02d}-{calendar.monthrange(2026, month)[1]:02d}",
        "gross": gross,
        "deductions": [{"name": n, "amount": a} for n, a in deductions],
        "reported_payout": payout,
    }


def test_full_flow_from_text(env):
    client, sessions, _ = env
    res = client.post("/contracts/text", json={"title": "가상 계약", "text": TEXT})
    assert res.status_code == 202 and res.json()["status"] == "처리중"
    cid = res.json()["id"]

    # 응답 뒤 처리 작업이 끝나 있다 (TestClient는 백그라운드 작업을 바로 실행)
    assert client.get(f"/contracts/{cid}").json()["status"] == "조건 확인 대기"
    assert len(client.get(f"/contracts/{cid}/clauses").json()) == 3
    assert [c["id"] for c in client.get("/contracts").json()] == [cid]
    other = client.get(f"/contracts/{cid}", headers={"X-User-Id": "u2"})
    assert other.status_code == 404

    s1 = client.post(f"/contracts/{cid}/statements", json=_statement(1, "1000000", "0"))
    assert s1.status_code == 201 and s1.json()["gross"] == "1000000"
    blocked = client.get(f"/contracts/{cid}/reconciliations")
    assert blocked.status_code == 409 and blocked.json()["detail"]["code"] == "TERMS_NOT_CONFIRMED"

    assert client.put(f"/contracts/{cid}/terms", json=CONFIRM).json()["all_confirmed"] is True
    client.post(
        f"/contracts/{cid}/statements",
        json=_statement(2, "1500000", "40000", [("앱마켓 수수료", "450000"), ("운영비", "1000")]),
    )
    report = client.get(f"/contracts/{cid}/reconciliations").json()
    m1, m2 = report["items"]
    assert (m1["computed_payout"], m1["mg_balance_after"], m1["diff"]) == ("0", "580000", "0")
    assert (m2["computed_payout"], m2["diff"]) == ("50000", "10000")  # 금액은 문자열
    assert m2["summary"].startswith("계약서 기준으로 계산하면 50,000원")
    assert any("운영비" in q for q in m2["questions"])
    assert report["rules_version"].startswith("provisional")

    client.get(f"/contracts/{cid}/reconciliations")  # 다시 조회해도 결과가 쌓이지 않는다
    with sessions() as s:
        assert s.scalar(select(func.count()).select_from(Reconciliation)) == 2

    sid = s1.json()["id"]
    assert client.delete(f"/contracts/{cid}/statements/{sid}").status_code == 204
    assert len(client.get(f"/contracts/{cid}/statements").json()) == 1

    assert client.delete(f"/contracts/{cid}").status_code == 204
    assert client.get(f"/contracts/{cid}").status_code == 404
    with sessions() as s:  # 정산서·대조 결과도 함께 지워진다
        assert s.scalar(select(func.count()).select_from(Statement)) == 0
        assert s.scalar(select(func.count()).select_from(Reconciliation)) == 0


def test_file_upload_and_failures(env):
    client, _, parser = env
    up = client.post(
        "/contracts", files={"file": ("가상.pdf", TEXT.encode("utf-8"), "application/pdf")}
    )
    assert up.status_code == 202 and up.json()["title"] == "가상"
    assert client.get(f"/contracts/{up.json()['id']}").json()["status"] == "조건 확인 대기"

    bad = client.post("/contracts", files={"file": ("a.exe", b"x", "application/octet-stream")})
    assert bad.status_code == 415 and bad.json()["detail"]["code"] == "UNSUPPORTED_FILE"
    empty = client.post("/contracts", files={"file": ("a.pdf", b"", "application/pdf")})
    assert empty.status_code == 422

    parser.fail = True
    failed = client.post("/contracts", files={"file": ("b.pdf", b"x", "application/pdf")})
    status = client.get(f"/contracts/{failed.json()['id']}").json()["status"]
    assert status == "처리 실패"

    no_clauses = client.post("/contracts/text", json={"title": "메모", "text": "조항이 없는 글"})
    assert client.get(f"/contracts/{no_clauses.json()['id']}").json()["status"] == "처리 실패"


def test_statement_validation(env):
    client, _, _ = env
    cid = client.post("/contracts/text", json={"title": "가상", "text": TEXT}).json()["id"]
    bad = _statement(1, "1,000,000", "0")
    assert client.post(f"/contracts/{cid}/statements", json=bad).status_code == 422
    missing = client.delete(f"/contracts/{cid}/statements/nope")
    assert missing.status_code == 404 and missing.json()["detail"]["code"] == "STATEMENT_NOT_FOUND"
