"""법령 근거 검색 (openbook.law): 법제처 응답 읽기, 색인 검색, Q&A 연결. 네트워크는 쓰지 않는다."""

from __future__ import annotations

import json
from datetime import date

import httpx
import pytest

from openbook.law import EmbeddingError, LawApiClient, LawApiError, LawArticle, LawIndex, parse_law
from openbook.qa import answer_question
from openbook.schemas import Clause

# 법제처 lawService.do 응답 모양 (실제 응답에서 확인한 필드, 내용은 줄임)
LAW_JSON = {
    "법령": {
        "기본정보": {"법령명_한글": "저작권법", "시행일자": "20260301"},
        "조문": {
            "조문단위": [
                {"조문여부": "전문", "조문내용": "제1장 총칙"},
                {
                    "조문여부": "조문",
                    "조문번호": "22",
                    "조문제목": "2차적저작물작성권",
                    "조문내용": "제22조(2차적저작물작성권) 저작자는 그의 저작물을 원저작물로 하는 "
                    "2차적저작물을 작성하여 이용할 권리를 가진다.",
                },
                {
                    "조문여부": "조문",
                    "조문번호": "59",
                    "조문제목": "배타적발행권의 존속기간 등",
                    "조문내용": "제59조(배타적발행권의 존속기간 등)",
                    "조문시행일자": "20240101",
                    "항": [
                        {
                            "항내용": "① 배타적발행권은 그 설정행위에 특약이 없는 때에는 3년간 존속한다."
                        },
                        {
                            "항내용": "② 다음 각 호의 경우에는 그러하지 아니하다.",
                            "호": {"호내용": "1. 특약이 있는 경우", "목": [{"목내용": "가. 예시"}]},
                        },
                    ],
                },
                {"조문여부": "조문", "조문번호": "60", "조문내용": "제60조 삭제 <2011. 12. 2.>"},
                {
                    "조문여부": "조문",
                    "조문번호": "35",
                    "조문가지번호": "2",
                    "조문내용": "제35조의2(저작물 이용과정에서의 일시적 복제) 컴퓨터에서 저작물을 "
                    "이용하는 경우에는 원활하고 효율적인 정보처리를 위하여 필요하다고 인정되는 범위에서 "
                    "그 저작물을 그 컴퓨터에 일시적으로 복제할 수 있다.",
                },
            ]
        },
    }
}


def test_parse_law_reads_articles_paragraphs_and_dates():
    arts = parse_law(LAW_JSON)
    assert [a.article_no for a in arts] == ["제22조", "제59조", "제35조의2"]  # 장 제목·삭제 조문 뺌
    a22, a59, a35 = arts
    assert a22.id == "l-저작권법-제22조" and a22.title == "2차적저작물작성권"
    assert a22.effective_date == date(2026, 3, 1)  # 조문 시행일이 없으면 법령 시행일
    assert a59.effective_date == date(2024, 1, 1)
    assert (
        "3년간 존속한다" in a59.text
        and "1. 특약이 있는 경우" in a59.text
        and "가. 예시" in a59.text
    )
    assert a35.source_url == "https://www.law.go.kr/법령/저작권법"


def test_parse_law_rejects_unexpected_shape():
    with pytest.raises(LawApiError):
        parse_law({"법령": {}})


class _Resp:
    def __init__(self, status=200, data=None, text=None):
        self.status_code, self._data, self._text = status, data, text

    def json(self):
        if self._text is not None:
            raise ValueError("not json")
        return self._data


def test_client_finds_exact_current_law_and_hides_oc(monkeypatch):
    calls = []

    def fake_get(url, params, timeout):
        calls.append((url, dict(params)))
        if url.endswith("lawSearch.do"):
            rows = [
                {"법령명한글": "저작권법 시행령", "법령일련번호": "1", "현행연혁코드": "현행"},
                {"법령명한글": "저작권법", "법령일련번호": "2", "현행연혁코드": "연혁"},
                {"법령명한글": "저작권법", "법령일련번호": "3", "현행연혁코드": "현행"},
            ]
            return _Resp(data={"LawSearch": {"law": rows}})
        return _Resp(data=LAW_JSON)

    monkeypatch.setattr(httpx, "get", fake_get)
    client = LawApiClient("secret-oc")
    assert len(client.articles("저작권법")) == 3
    assert calls[1][1]["MST"] == "3"  # 이름이 정확히 같고 현행인 것

    monkeypatch.setattr(httpx, "get", lambda url, params, timeout: _Resp(text="<html>"))
    with pytest.raises(LawApiError) as e:
        client.find_current("저작권법")
    assert "secret-oc" not in str(e.value)
    monkeypatch.setattr(httpx, "get", lambda url, params, timeout: _Resp(status=500))
    with pytest.raises(LawApiError, match="HTTP 500"):
        client.find_current("저작권법")
    with pytest.raises(ValueError):
        LawApiClient("")


# ---------------------------------------------------------------- 색인 검색


def art(no, title, text):
    return LawArticle(id=f"l-가상법-{no}", law_name="가상법", article_no=no, title=title, text=text)


ARTICLES = [
    art("제1조", "목적", "이 법은 가상 저작물의 이용 질서를 정하는 것을 목적으로 한다."),
    art("제2조", "2차적저작물작성권", "저작자는 2차적저작물을 작성하여 이용할 권리를 가진다."),
    art("제3조", "배타적발행권의 존속기간", "배타적발행권은 특약이 없으면 3년간 존속한다."),
    art("제4조", "불공정행위의 금지", "예술인에게 불공정한 계약 조건을 강요해서는 아니 된다."),
]
# 질문별로 정해 둔 벡터 (가상 임베딩). 조문 i와 질문의 코사인이 원하는 값이 되게 한다.
VECTORS = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]


class FakeEmbedder:
    def __init__(self, query_vector=None, fail=False):
        self.q, self.fail, self.calls = query_vector, fail, 0

    def embed_passages(self, texts):
        raise AssertionError("검색 때는 조문을 임베딩하지 않는다")

    def embed_query(self, text):
        self.calls += 1
        if self.fail:
            raise EmbeddingError("임베딩 호출 실패: HTTP 500")
        return self.q


def test_keyword_search_prefers_matching_title():
    idx = LawIndex(ARTICLES)
    assert idx.search("2차적저작물 작성권은 누구에게 있나요?")[0].article_no == "제2조"
    assert idx.search("배타적발행권 존속기간은?")[0].article_no == "제3조"


def test_keyword_only_returns_nothing_for_unrelated_question():
    assert LawIndex(ARTICLES).search("MG는 언제 지급되나요?") == []


def test_vector_finds_meaning_and_gate_blocks_unrelated():
    idx = LawIndex(ARTICLES, VECTORS)
    # 글자는 안 겹치지만 뜻(벡터)이 제4조에 가까운 질문
    near = FakeEmbedder([0, 0, 0.1, 1])
    assert idx.search("갑질 당하면 어떻게 하나요", near)[0].article_no == "제4조"
    close = FakeEmbedder([0.1, 0.1, 0.1, 1.0])  # 제4조와 0.98 → 기준 통과
    assert idx.search("불공정한 계약", close)[0].article_no == "제4조"
    # 가장 가까운 조문도 기준 미만이면 글자가 겹쳐도 법령을 붙이지 않는다
    unrelated = FakeEmbedder([0.2, 0.2, 0.2, -1.0])  # 모든 조문과 0.19 이하
    assert idx.search("2차적저작물 불공정한 계약", unrelated) == []


def test_embedding_failure_falls_back_to_keywords():
    idx = LawIndex(ARTICLES, VECTORS)
    broken = FakeEmbedder(fail=True)
    assert idx.search("2차적저작물 작성권", broken)[0].article_no == "제2조"
    assert broken.calls == 1


def test_index_round_trip_and_size_check(tmp_path):
    path = tmp_path / "law" / "index.json"
    LawIndex(ARTICLES, VECTORS).save(path)
    again = LawIndex.load(path)
    assert again.articles == ARTICLES and again.vectors == [list(map(float, v)) for v in VECTORS]
    assert json.loads(path.read_text(encoding="utf-8"))["articles"][0]["law_name"] == "가상법"
    with pytest.raises(ValueError):
        LawIndex(ARTICLES, VECTORS[:2])


# ---------------------------------------------------------------- Q&A 연결

CLAUSES = [Clause(id="c-01", no="제7조", title="2차적 사용", text="2차적 사용은 별도로 협의한다.")]
LAW = [
    LawArticle(
        id="l-저작권법-제22조",
        law_name="저작권법",
        article_no="제22조",
        title="2차적저작물작성권",
        text="저작자는 그의 저작물을 원저작물로 하는 2차적저작물을 작성하여 이용할 권리를 가진다.",
        effective_date=date(2026, 3, 1),
        source_url="https://www.law.go.kr/법령/저작권법",
    )
]


class FakeLLM:
    def __init__(self, data):
        self.raw, self.calls = json.dumps(data, ensure_ascii=False), []

    def complete(self, system, user):
        self.calls.append(user)
        return self.raw


def test_qa_cites_law_with_name_date_and_link():
    llm = FakeLLM(
        {
            "found": True,
            "answer": "계약서 제7조는 별도 협의라고 적혀 있고, 저작권법 제22조는 저작자의 권리로 정합니다.",
            "citations": [
                {"clause_id": "c-01", "quote": "2차적 사용은 별도로 협의한다."},
                {
                    "clause_id": "l-저작권법-제22조",
                    "quote": "저작자는 그의 저작물을 원저작물로 하는 2차적저작물을 작성하여 이용할 "
                    "권리를 가진다.",
                },
            ],
        }
    )
    out = answer_question("k1", "2차 사용 권리는 누구에게?", CLAUSES, llm, [], LAW)
    assert "=== 관련 법령 (참고) ===" in llm.calls[0] and "[l-저작권법-제22조]" in llm.calls[0]
    assert out.found and out.answer.startswith("계약서 제7조")  # 22·7은 조문 번호라 허용
    law = out.citations[1]
    assert (law.source, law.law_name, law.clause_no) == ("law", "저작권법", "제22조")
    assert law.effective_date == date(2026, 3, 1) and law.source_url.endswith("저작권법")


def test_qa_drops_invented_law_quote_and_skips_law_block_when_empty():
    llm = FakeLLM(
        {
            "found": True,
            "answer": "저작권법 제22조에 적혀 있습니다.",
            "citations": [
                {"clause_id": "l-저작권법-제22조", "quote": "모든 권리는 출판사에 있다."}
            ],
        }
    )
    out = answer_question("k1", "권리는?", CLAUSES, llm, [], LAW)
    assert not out.found and out.citations == []
    llm2 = FakeLLM({"found": False, "answer": "", "citations": []})
    answer_question("k1", "권리는?", CLAUSES, llm2, [], [])
    assert "관련 법령" not in llm2.calls[0]


def test_evaluate_counts_hits_and_abstentions():
    from openbook.law.evaluate import evaluate, unknown_labels

    idx = LawIndex(ARTICLES)
    cases = [
        {"q": "2차적저작물 작성권은 누구에게?", "expect": ["가상법 제2조"]},
        {"q": "배타적발행권 존속기간은?", "expect": ["가상법 제1조"]},  # 일부러 틀린 정답
        {"q": "MG는 언제 지급되나요?", "expect": []},
    ]
    report = evaluate(idx, cases)
    assert [r.ok for r in report.rows] == [True, False, True]
    assert report.hit_rate == 0.5 and report.abstain_rate == 1.0
    assert unknown_labels(idx, [{"q": "x", "expect": ["가상법 제9조"]}]) == ["가상법 제9조"]
