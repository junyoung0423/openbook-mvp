import json

from openbook.comparison import StandardClause
from openbook.qa import NOT_FOUND_ANSWER, QA_NOTICE, answer_question
from openbook.qa.answer import _related_standard
from openbook.schemas import Clause

# 가상의 조항 (실제 계약서 아님)
CLAUSES = [
    Clause(
        id="c-01",
        no="제4조",
        title="선급금",
        text="갑은 을에게 선급금 5,000,000원을 지급한다.\n선급금은 을의 수익배분금에서 우선 차감한다.",
    ),
    Clause(id="c-02", no="제5조", title="수익배분", text="을의 수익배분율은 순매출의 60%로 한다."),
]
STANDARD = [
    StandardClause(
        id="s-10",
        no="제10조",
        title="정산 등",
        text="‘저작권자’와 ‘서비스 제공업자’는 수익분배 비율에 따라 순 매출액을 나누어 갖는다.",
    ),
    StandardClause(
        id="s-26", no="제26조", title="비밀유지", text="영업상 비밀 정보를 공개하지 않는다."
    ),
]


class FakeLLM:
    def __init__(self, data=None, raw=None):
        self.raw = raw if raw is not None else json.dumps(data, ensure_ascii=False)
        self.calls = []

    def complete(self, system, user):
        self.calls.append((system, user))
        return self.raw


def ask(question, data=None, raw=None):
    llm = FakeLLM(data, raw)
    return answer_question("k1", question, CLAUSES, llm, STANDARD), llm


def test_answer_with_verified_quote():
    out, llm = ask(
        "선급금은 얼마고 어떻게 회수하나요?",
        {
            "found": True,
            "answer": "제4조에 선급금 5,000,000원을 수익배분금에서 우선 차감한다고 적혀 있습니다.",
            "citations": [
                {"clause_id": "c-01", "quote": "갑은 을에게 선급금 5,000,000원을 지급한다."}
            ],
        },
    )
    assert out.found and out.citations[0].clause_no == "제4조"
    assert out.citations[0].source == "contract" and out.basis is None
    assert "5,000,000원" in out.answer and out.notice == QA_NOTICE
    assert len(llm.calls) == 1  # LLM은 한 번만 부른다


def test_invented_quote_is_dropped_and_becomes_not_found():
    out, _ = ask(
        "MG는 얼마인가요?",
        {
            "found": True,
            "answer": "선급금은 1,000만 원입니다.",
            "citations": [
                {"clause_id": "c-01", "quote": "갑은 을에게 선급금 10,000,000원을 지급한다."}
            ],
        },
    )
    assert not out.found and out.answer == NOT_FOUND_ANSWER and out.citations == []
    assert any("확인되지 않은 인용 1개" in w for w in out.warnings)


def test_calculated_number_is_replaced_with_template():
    # 60%에서 40%를 계산해 낸 답은 쓰지 않는다 (LLM은 계산하지 않는다)
    out, _ = ask(
        "플랫폼 몫은 몇 %인가요?",
        {
            "found": True,
            "answer": "을이 60%를 받으므로 플랫폼은 40%를 가져갑니다.",
            "citations": [{"clause_id": "c-02", "quote": "을의 수익배분율은 순매출의 60%로 한다."}],
        },
    )
    assert out.found and "40" not in out.answer and "대조 화면" in out.answer
    assert any("원문에 없는 숫자" in w for w in out.warnings)


def test_banned_word_is_replaced_with_template():
    out, _ = ask(
        "선급금 조항 괜찮나요?",
        {
            "found": True,
            "answer": "이 조항은 작가에게 불리합니다.",
            "citations": [
                {"clause_id": "c-01", "quote": "선급금은 을의 수익배분금에서 우선 차감한다."}
            ],
        },
    )
    assert "불리" not in out.answer and out.found


def test_standard_citation_carries_basis():
    out, _ = ask(
        "표준계약서에서는 매출을 어떻게 나누나요?",
        {
            "found": True,
            "answer": "표준계약서 제10조는 순 매출액을 수익분배 비율에 따라 나눈다고 적습니다.",
            "citations": [
                {"clause_id": "s-10", "quote": "수익분배 비율에 따라 순 매출액을 나누어 갖는다"}
            ],
        },
    )
    assert out.citations[0].source == "standard"
    assert out.basis and "제2024-32호" in out.basis


def test_not_found_and_unreadable_answers():
    out, _ = ask("해외 출판은 어떻게 되나요?", {"found": False, "answer": "", "citations": []})
    assert not out.found and out.answer == NOT_FOUND_ANSWER
    out, _ = ask("아무 질문", raw="죄송합니다")
    assert not out.found and out.warnings


def test_related_standard_picks_overlapping_clauses_only():
    picked = _related_standard("순 매출액 나누는 비율", STANDARD)
    assert [s.id for s in picked] == ["s-10"]
    assert _related_standard("zzz", STANDARD) == []


def test_question_and_contract_text_not_in_warnings():
    out, _ = ask(
        "선급금 5,000,000원 질문",
        {"found": True, "answer": "x", "citations": [{"clause_id": "c-99", "quote": "없는 문장"}]},
    )
    assert not any("선급금" in w or "5,000,000" in w for w in out.warnings)
