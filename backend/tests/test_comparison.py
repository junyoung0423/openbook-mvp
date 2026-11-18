import json

import pytest

from openbook.comparison import DISCLAIMER, compare_with_standard, load_standard
from openbook.comparison.compare import TEMPLATE_DIFFERENCE
from openbook.comparison.models import StandardClause
from openbook.safety import is_clean
from openbook.schemas import Clause
from openbook.terms.llm import LLMError

# 테스트용으로 지어낸 조항이다. 실제 표준계약서 원문이 아니다.
STANDARD = [
    StandardClause(
        id="s-01",
        no="제1조",
        title="계약기간",
        text="이 계약의 기간은 계약 체결일로부터 3년으로 한다.",
        core=True,
    ),
    StandardClause(
        id="s-02",
        no="제2조",
        title="내용 변경",
        text="갑은 을의 동의 없이 작품의 내용을 변경하지 않는다.",
    ),
    StandardClause(
        id="s-03",
        no="제3조",
        title="자료 제공",
        text="갑은 을의 요청이 있으면 판매 자료를 제공한다.",
    ),
]

CLAUSES = [
    Clause(
        id="c-01",
        no="제1조",
        title="계약기간",
        text="이 계약의 기간은 계약 체결일로부터\n  7년으로 한다.",
    ),
    Clause(
        id="c-02",
        no="제2조",
        title="작품 수정",
        text="갑은 을의 동의 없이 작품을 수정하지 않는다.",
    ),
]

GOOD = [
    {
        "standard_id": "s-01",
        "status": "different",
        "user_clause_id": "c-01",
        "difference": "계약기간이 표준은 3년, 계약서는 7년입니다.",
        "user_quote": "이 계약의 기간은 계약 체결일로부터 7년으로 한다.",
        "standard_quote": "이 계약의 기간은 계약 체결일로부터 3년으로 한다.",
    },
    {"standard_id": "s-02", "status": "none_detected", "user_clause_id": "c-02"},
    {"standard_id": "s-03", "status": "not_found", "user_clause_id": None},
]


class FakeLLM:
    def __init__(self, rows=None, raw=None):
        self.raw = raw if raw is not None else json.dumps({"comparisons": rows}, ensure_ascii=False)
        self.calls = []

    def complete(self, system, user):
        self.calls.append((system, user))
        return self.raw


def run(rows=None, raw=None):
    return compare_with_standard("k1", CLAUSES, STANDARD, FakeLLM(rows, raw))


def with_row(idx, **changes):
    rows = [dict(r) for r in GOOD]
    rows[idx].update(changes)
    return rows


def test_good_answer_keeps_statuses_and_quotes():
    r = run(GOOD)
    assert [i.status for i in r.items] == ["different", "none_detected", "not_found"]
    first = r.items[0]
    assert first.user_clause_id == "c-01"
    assert first.core is True and first.standard_no == "제1조"
    assert "7년" in first.user_quote and "3년" in first.standard_quote
    assert first.notice is None
    assert r.warnings == []


def test_not_different_items_carry_disclaimer():
    r = run(GOOD)
    assert r.items[1].notice == DISCLAIMER
    assert r.items[2].notice == DISCLAIMER
    assert r.disclaimer == DISCLAIMER


def test_prompt_contains_both_sides():
    llm = FakeLLM(GOOD)
    compare_with_standard("k1", CLAUSES, STANDARD, llm)
    system, user = llm.calls[0]
    assert "부정문" in system
    assert "[s-02] 제2조 내용 변경" in user and "[c-02] 제2조 작품 수정" in user


def test_invented_user_quote_becomes_needs_check():
    r = run(with_row(0, user_quote="이 계약의 기간은 10년으로 한다."))
    assert r.items[0].status == "needs_check"
    assert r.items[0].difference is None and r.items[0].user_quote is None
    assert r.items[0].notice == DISCLAIMER
    assert r.warnings


def test_invented_standard_quote_becomes_needs_check():
    r = run(with_row(0, standard_quote="계약기간은 2년으로 한다."))
    assert r.items[0].status == "needs_check"


def test_missing_quote_becomes_needs_check():
    r = run(with_row(0, user_quote=None))
    assert r.items[0].status == "needs_check"


def test_unknown_user_clause_becomes_needs_check():
    r = run(with_row(1, user_clause_id="c-99"))
    assert r.items[1].status == "needs_check"
    assert r.items[1].user_clause_id is None


def test_quote_from_other_clause_is_rejected():
    # 인용문은 c-01에 있는데 c-02를 가리키면 통과시키지 않는다
    r = run(with_row(0, user_clause_id="c-02"))
    assert r.items[0].status == "needs_check"


def test_banned_words_in_difference_replaced_with_template():
    r = run(with_row(0, difference="계약기간이 표준보다 길어 작가에게 불리합니다."))
    assert r.items[0].status == "different"
    assert r.items[0].difference == TEMPLATE_DIFFERENCE
    assert is_clean(r.items[0].difference)
    assert any("금지 표현" in w for w in r.warnings)


def test_empty_difference_gets_template():
    r = run(with_row(0, difference=""))
    assert r.items[0].difference == TEMPLATE_DIFFERENCE


def test_missing_standard_clause_becomes_needs_check():
    r = run(GOOD[:2])
    assert len(r.items) == 3
    assert r.items[2].status == "needs_check"
    assert any("표준 제3조 자료 제공" in w for w in r.warnings)
    assert all("s-0" not in w for w in r.warnings)


def test_unknown_status_becomes_needs_check():
    r = run(with_row(1, status="same"))
    assert r.items[1].status == "needs_check"


def test_unparseable_answer_marks_everything_needs_check():
    r = run(raw="죄송합니다, 답할 수 없습니다.")
    assert [i.status for i in r.items] == ["needs_check"] * 3
    assert r.warnings


def test_code_fenced_answer_is_parsed():
    raw = "```json\n" + json.dumps({"comparisons": GOOD}, ensure_ascii=False) + "\n```"
    assert run(raw=raw).items[0].status == "different"


def test_llm_error_propagates():
    class Broken:
        def complete(self, system, user):
            raise LLMError("연결 실패")

    with pytest.raises(LLMError):
        compare_with_standard("k1", CLAUSES, STANDARD, Broken())


def test_load_standard_yaml(tmp_path):
    p = tmp_path / "std.yaml"
    p.write_text(
        "clauses:\n  - id: s-01\n    no: 제1조\n    core: true\n    text: |\n      원문입니다.\n",
        encoding="utf-8",
    )
    [c] = load_standard(p)
    assert c.id == "s-01" and c.core is True and c.text.strip() == "원문입니다."


def test_load_standard_rejects_duplicate_ids(tmp_path):
    p = tmp_path / "std.json"
    p.write_text('[{"id": "s-01", "text": "a"}, {"id": "s-01", "text": "b"}]', encoding="utf-8")
    with pytest.raises(ValueError):
        load_standard(p)
