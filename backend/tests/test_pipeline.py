import json
from pathlib import Path

from openbook.pipeline import process_contract
from openbook.schemas import TermKey, TermStatus
from openbook.terms.llm import LLMError

SAMPLES = Path(__file__).resolve().parents[2] / "data" / "samples"
SAMPLE_A = (SAMPLES / "sample_a.txt").read_text(encoding="utf-8")

MG_QUOTE = '갑은 을에게 선급금(이하 "MG") 5,000,000원을 계약 체결일로부터 30일 이내에 지급한다.'
RS_QUOTE = "을의 수익배분율은 순매출의 60%로 한다."
ANSWER = json.dumps(
    {
        "terms": [
            {"key": "mg_amount", "value": "5000000", "clause_id": "c-04", "quote": MG_QUOTE},
            {"key": "rs_rate", "value": "0.6", "clause_id": "c-05", "quote": RS_QUOTE},
            {"key": "revenue_base", "value": "net", "clause_id": "c-05", "quote": RS_QUOTE},
        ]
    },
    ensure_ascii=False,
)


class FakeLLM:
    def __init__(self, answer=ANSWER, error=None):
        self.answer, self.error, self.calls = answer, error, 0

    def complete(self, system, user):
        self.calls += 1
        if self.error:
            raise self.error
        return self.answer


def term(result, key):
    return next(t for t in result.terms.terms if t.key == key)


def test_ok_path_returns_clauses_and_terms():
    res = process_contract("k1", SAMPLE_A, FakeLLM())
    assert res.contract_id == "k1" and res.clause_style == "article"
    assert len(res.clauses) == 10 and not res.clause_review_needed
    assert res.error is None
    assert term(res, TermKey.MG_AMOUNT).status is TermStatus.EXTRACTED
    assert term(res, TermKey.PAYMENT_DAY).status is TermStatus.NOT_FOUND  # 답에 없는 항목
    assert not res.terms.all_confirmed


def test_no_clauses_skips_extraction_entirely():
    llm = FakeLLM()
    res = process_contract("k2", "번호도 제목도 없는 한 덩어리 글입니다.", llm)
    assert res.clauses == [] and res.clause_review_needed and res.terms is None
    assert res.clause_style == "none" and res.error is None
    assert llm.calls == 0  # 근거 문장이 없으니 LLM에 계약서를 보내지 않는다


def test_uncertain_split_still_extracts_but_asks_for_review():
    # 제3조 제목이 빠져 이후 조항이 앞 조항에 합쳐짐: 사용자 확인이 필요하지만, 나뉜 조항에서는 추출한다
    res = process_contract("k3", SAMPLE_A.replace("제3조 (계약기간)", "계약기간"), FakeLLM())
    assert res.clause_review_needed
    assert res.terms is not None
    assert (
        term(res, TermKey.MG_AMOUNT).status is TermStatus.EXTRACTED
    )  # 인용문이 있는 조항으로 바로잡힘
    assert any("차례" in w for w in res.warnings)


def test_llm_failure_keeps_clauses_and_reports_error():
    res = process_contract("k4", SAMPLE_A, FakeLLM(error=LLMError("Upstage 호출 실패: HTTP 500")))
    assert len(res.clauses) == 10 and res.terms is None
    assert res.error and "HTTP 500" in res.error
    assert "선급금" not in res.error  # 오류 문구에 계약서 내용이 들어가지 않는다


def test_warnings_from_split_and_extraction_are_merged():
    bad_quote = json.dumps(
        {
            "terms": [
                {
                    "key": "rs_rate",
                    "value": "0.7",
                    "clause_id": "c-05",
                    "quote": "순매출의 70%로 한다.",
                }
            ]
        },
        ensure_ascii=False,
    )
    res = process_contract("k5", SAMPLE_A, FakeLLM(answer=bad_quote))
    assert term(res, TermKey.RS_RATE).status is TermStatus.NOT_FOUND
    assert any("rs_rate" in w for w in res.warnings)


def test_result_serializes_to_plain_json():
    res = process_contract("k6", SAMPLE_A, FakeLLM())
    dumped = res.model_dump(mode="json")
    json.dumps(dumped, ensure_ascii=False)  # 예외가 나지 않아야 한다
    mg = next(t for t in dumped["terms"]["terms"] if t["key"] == "mg_amount")
    assert mg["value"] == "5000000"  # Decimal은 문자열로 나간다
