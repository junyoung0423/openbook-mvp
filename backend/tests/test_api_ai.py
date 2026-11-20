import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from openbook.api.deps import get_db, get_llm
from openbook.api.main import app
from openbook.api.routes import ai
from openbook.db import (
    Base,
    ClauseRecord,
    Contract,
    QaLog,
    User,
    create_db_engine,
    make_session_factory,
    term_to_record,
)
from openbook.schemas import Term, TermKey, TermStatus
from openbook.terms.llm import LLMError

# 모두 가상의 계약서·값이다 (실제 계약서 아님)
C01 = "갑은 을에게 선급금 5,000,000원을 지급한다. 선급금은 을의 수익배분금에서 우선 차감한다."
C02 = "을의 수익배분율은 순매출의 60%로 한다."


class FakeLLM:
    def __init__(self, raw="{}", fail=False):
        self.raw, self.fail, self.calls = raw, fail, 0

    def complete(self, system, user):
        self.calls += 1
        if self.fail:
            raise LLMError("Upstage 호출 실패: HTTP 500")
        return self.raw


def _terms():
    found = {
        TermKey.MG_AMOUNT: ("5000000", "c-01", "선급금 5,000,000원을 지급한다"),
        TermKey.MG_RECOUP: ("from_rs", "c-01", "을의 수익배분금에서 우선 차감한다"),
        TermKey.RS_RATE: ("0.6", "c-02", "을의 수익배분율은 순매출의 60%로 한다."),
        TermKey.REVENUE_BASE: ("net", "c-02", "을의 수익배분율은 순매출의 60%로 한다."),
    }
    out = []
    for key in TermKey:
        if key in found:
            v, cid, q = found[key]
            out.append(
                Term(key=key, value=v, status=TermStatus.EXTRACTED, source_clause_id=cid, quote=q)
            )
        else:
            out.append(Term(key=key, status=TermStatus.NOT_FOUND))
    return out


@pytest.fixture
def env(tmp_path):
    engine = create_db_engine(f"sqlite:///{tmp_path / 'api.db'}")
    Base.metadata.create_all(engine)
    sessions = make_session_factory(engine)
    with sessions.begin() as s:
        me, other = User(id="u1", email="me@example.test"), User(id="u2", email="o@example.test")
        mine = Contract(id="k1", user=me, title="가상 계약", status="조건 확인 대기")
        theirs = Contract(id="k2", user=other, title="남의 계약", status="조건 확인 대기")
        empty = Contract(id="k3", user=me, title="조항 없음", status="처리중")
        s.add_all([mine, theirs, empty])
        s.flush()
        s.add_all(
            [
                ClauseRecord(contract_id="k1", id="c-01", no="제4조", title="선급금", text=C01),
                ClauseRecord(contract_id="k1", id="c-02", no="제5조", title="수익배분", text=C02),
            ]
        )
        s.add_all([term_to_record("k1", t) for t in _terms()])

    def _db():
        with sessions() as s:
            yield s

    llm = FakeLLM()
    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_llm] = lambda: llm
    ai._comparisons.clear()
    client = TestClient(app, headers={"X-User-Id": "u1"})
    yield client, llm, sessions
    app.dependency_overrides.clear()
    engine.dispose()


def test_auth_and_ownership(env):
    client, _, _ = env
    assert client.get("/contracts/k1/terms", headers={"X-User-Id": ""}).status_code == 401
    res = client.get("/contracts/k2/terms")  # 남의 계약서는 없는 것처럼
    assert res.status_code == 404 and res.json()["detail"]["code"] == "CONTRACT_NOT_FOUND"


def test_get_terms_lists_what_to_confirm(env):
    client, _, _ = env
    body = client.get("/contracts/k1/terms").json()
    assert [t["key"] for t in body["terms"]] == [k.value for k in TermKey]
    assert body["all_confirmed"] is False and body["missing_keys"] == []
    assert body["unconfirmed_required"] == [
        "mg_amount",
        "mg_recoup",
        "rs_rate",
        "revenue_base",
        "deductions",
    ]
    mg = body["terms"][0]
    assert mg["value"] == "5000000" and mg["status"] == "extracted"  # 금액은 문자열


def test_confirm_keeps_extracted_and_server_sets_time(env):
    client, _, _ = env
    body = client.put(
        "/contracts/k1/terms",
        json={"terms": [{"key": "mg_amount", "value": "5000000", "confirmed": True}]},
    ).json()
    mg = body["terms"][0]
    assert mg["status"] == "extracted" and mg["confirmed"] and mg["confirmed_at"]
    assert mg["source_clause_id"] == "c-01"
    assert "mg_amount" not in body["unconfirmed_required"]


def test_changed_value_becomes_user_input_and_keeps_quote(env):
    client, _, _ = env
    body = client.put(
        "/contracts/k1/terms",
        json={"terms": [{"key": "rs_rate", "value": "0.7", "confirmed": False}]},
    ).json()
    rs = next(t for t in body["terms"] if t["key"] == "rs_rate")
    assert rs["value"] == "0.7" and rs["status"] == "user_input"
    assert rs["quote"] and not rs["confirmed"] and rs["confirmed_at"] is None


@pytest.mark.parametrize(
    "update",
    [
        {"key": "rs_rate", "value": 0.7, "confirmed": True},  # float 거절
        {"key": "mg_amount", "value": "오백만", "confirmed": True},
        {"key": "deductions", "confirmed": True},  # 찾지 못한 값은 입력 없이 확정 못 함
    ],
)
def test_invalid_updates_are_rejected_without_saving(env, update):
    client, _, _ = env
    res = client.put("/contracts/k1/terms", json={"terms": [update]})
    assert res.status_code == 422 and res.json()["detail"]["code"] == "INVALID_TERM"
    after = client.get("/contracts/k1/terms").json()
    assert not any(t["confirmed"] for t in after["terms"])


def test_confirming_required_five_opens_reconciliation(env):
    client, _, sessions = env
    updates = [
        {"key": "mg_amount", "confirmed": True},
        {"key": "mg_recoup", "confirmed": True},
        {"key": "rs_rate", "confirmed": True},
        {"key": "revenue_base", "confirmed": True},
        {
            "key": "deductions",
            "value": [{"name": "앱마켓 수수료", "rate": "0.3"}],
            "confirmed": True,
        },
    ]
    body = client.put("/contracts/k1/terms", json={"terms": updates}).json()
    assert body["all_confirmed"] is True and body["unconfirmed_required"] == []
    with sessions() as s:
        assert s.get(Contract, "k1").status == "확정"
    # 하나를 확정 취소하면 다시 대기
    client.put("/contracts/k1/terms", json={"terms": [{"key": "rs_rate", "confirmed": False}]})
    with sessions() as s:
        assert s.get(Contract, "k1").status == "조건 확인 대기"


def test_comparison_is_cached_and_llm_failure_is_502(env):
    client, llm, _ = env
    first = client.get("/contracts/k1/comparison")
    assert first.status_code == 200 and len(first.json()["items"]) == 6  # 정산 관련 핵심 조항
    client.get("/contracts/k1/comparison")
    assert llm.calls == 1
    client.get("/contracts/k1/comparison?refresh=true")
    assert llm.calls == 2
    llm.fail = True
    res = client.get("/contracts/k1/comparison?refresh=true")
    assert res.status_code == 502 and res.json()["detail"]["code"] == "LLM_FAILED"
    assert client.get("/contracts/k3/comparison").json()["detail"]["code"] == "NO_CLAUSES"


def test_qa_answers_and_logs(env):
    client, llm, sessions = env
    llm.raw = json.dumps(
        {
            "found": True,
            "answer": "제4조에 선급금 5,000,000원이 적혀 있습니다.",
            "citations": [
                {"clause_id": "c-01", "quote": "갑은 을에게 선급금 5,000,000원을 지급한다."}
            ],
        },
        ensure_ascii=False,
    )
    res = client.post("/contracts/k1/qa", json={"question": "  선급금은 얼마인가요?  "})
    body = res.json()
    assert res.status_code == 200 and body["found"] and body["citations"][0]["clause_no"] == "제4조"
    with sessions() as s:
        log = s.scalars(select(QaLog)).one()
        assert log.question == "선급금은 얼마인가요?" and log.cited_clause_ids == ["c-01"]
    assert client.post("/contracts/k1/qa", json={"question": "   "}).status_code == 422
    llm.fail = True
    res = client.post("/contracts/k1/qa", json={"question": "MG는?"})
    assert res.status_code == 502 and "선급금" not in res.text


def test_statement_paste(env):
    client, llm, _ = env
    res = client.post(
        "/contracts/k1/statements/paste",
        json={"text": "정산 기간\t2026-10\n총매출\t1,000,000\n수수료\t300,000\n지급액\t420,000"},
    )
    body = res.json()
    assert res.status_code == 200 and body["gross"] == "1000000" and body["missing"] == []
    assert llm.calls == 0  # LLM을 부르지 않는다
    too_long = client.post("/contracts/k1/statements/paste", json={"text": "x" * 20_001})
    assert too_long.status_code == 422


def test_save_process_result_replaces_clauses_and_terms(env):
    client, _, sessions = env
    from openbook.api.process_store import save_process_result
    from openbook.pipeline import ProcessResult
    from openbook.schemas import Clause, TermSet

    result = ProcessResult(
        contract_id="k3",
        clause_style="article",
        clause_review_needed=False,
        clauses=[Clause(id="c-01", no="제1조", title="선급금", text=C01)],
        terms=TermSet(contract_id="k3", terms=_terms()),
    )
    for _ in range(2):  # 다시 처리해도 중복되지 않는다
        with sessions.begin() as s:
            save_process_result(s, s.get(Contract, "k3"), result)
    body = client.get("/contracts/k3/terms").json()
    assert len(body["terms"]) == 9 and body["missing_keys"] == []
    with sessions() as s:
        assert s.get(Contract, "k3").status == "조건 확인 대기"
        assert (
            len(s.scalars(select(ClauseRecord).where(ClauseRecord.contract_id == "k3")).all()) == 1
        )
    with sessions.begin() as s, pytest.raises(ValueError):
        save_process_result(s, s.get(Contract, "k1"), result)


def test_failed_extraction_still_lets_user_fill_and_confirm(env):
    client, _, sessions = env
    from openbook.api.process_store import save_process_result
    from openbook.pipeline import ProcessResult
    from openbook.schemas import Clause

    failed = ProcessResult(
        contract_id="k3",
        clause_style="article",
        clause_review_needed=False,
        clauses=[Clause(id="c-01", no="제1조", title="선급금", text=C01)],
        terms=None,
        error="조건 추출 호출에 실패했습니다: Upstage 호출 실패: HTTP 500",
    )
    with sessions.begin() as s:
        save_process_result(s, s.get(Contract, "k3"), failed)
    body = client.get("/contracts/k3/terms").json()
    assert body["missing_keys"] == [] and all(t["status"] == "not_found" for t in body["terms"])
    updates = [
        {"key": "mg_amount", "value": "5000000", "confirmed": True},
        {"key": "mg_recoup", "value": "from_rs", "confirmed": True},
        {"key": "rs_rate", "value": "0.6", "confirmed": True},
        {"key": "revenue_base", "value": "net", "confirmed": True},
        {"key": "deductions", "value": [], "confirmed": True},
    ]
    body = client.put("/contracts/k3/terms", json={"terms": updates}).json()
    assert body["all_confirmed"] is True
    assert all(t["status"] == "user_input" for t in body["terms"] if t["confirmed"])


def test_missing_api_key_is_503_not_500(env, monkeypatch):
    client, _, _ = env
    del app.dependency_overrides[get_llm]
    monkeypatch.setattr("openbook.terms.llm.load_dotenv", lambda: None)
    monkeypatch.delenv("UPSTAGE_API_KEY", raising=False)
    res = client.post("/contracts/k1/qa", json={"question": "선급금은?"})
    assert res.status_code == 503 and res.json()["detail"]["code"] == "LLM_NOT_CONFIGURED"
    assert client.get("/contracts/k1/terms").status_code == 200  # LLM이 필요 없는 곳은 그대로
