import json
from pathlib import Path

import pytest

from openbook.clauses import split_clauses

SAMPLES = Path(__file__).resolve().parents[2] / "data" / "samples"
EXPECTED = json.loads((SAMPLES / "expected_clauses.json").read_text(encoding="utf-8"))
SAMPLE_FILES = [k for k in EXPECTED if k.endswith(".txt")]


# ---- 샘플 계약서 (사람이 직접 센 정답과 대조)


@pytest.mark.parametrize("name", SAMPLE_FILES)
def test_samples_match_hand_counted_answers(name):
    out = split_clauses((SAMPLES / name).read_text(encoding="utf-8"))
    assert [c.no for c in out.clauses] == EXPECTED[name]["clause_nos"]
    assert [c.title for c in out.clauses] == EXPECTED[name]["titles"]
    assert not out.needs_llm and not out.warnings


def test_sample_styles():
    a = split_clauses((SAMPLES / "sample_a.txt").read_text(encoding="utf-8"))
    b = split_clauses((SAMPLES / "sample_b.txt").read_text(encoding="utf-8"))
    assert a.style == "article" and b.style == "numbered"


def test_clause_text_is_verbatim_and_complete():
    raw = (SAMPLES / "sample_a.txt").read_text(encoding="utf-8")
    out = split_clauses(raw)
    # 모든 조항 원문은 원본 텍스트 안에 그대로 들어 있다 (요약·수정 없음)
    assert all(c.text in raw for c in out.clauses)
    mg = next(c for c in out.clauses if c.no == "제4조")
    assert "5,000,000원" in mg.text
    assert mg.text.startswith("제4조 (선급금)")


def test_signature_block_trimmed_from_last_clause():
    out = split_clauses((SAMPLES / "sample_a.txt").read_text(encoding="utf-8"))
    last = out.clauses[-1]
    assert last.no == "제10조"
    assert "달빛출판 주식회사 (대표" not in last.text
    assert "2026년 12월 1일" not in last.text
    assert last.text.rstrip().endswith("지급한다.")


def test_sub_items_do_not_become_clauses():
    # 제6조 안의 "1. 결제 수수료", "2. 마케팅 비용" 호는 조항이 아니다
    out = split_clauses((SAMPLES / "sample_a.txt").read_text(encoding="utf-8"))
    c6 = next(c for c in out.clauses if c.no == "제6조")
    assert "1. 결제 수수료" in c6.text and "2. 마케팅 비용" in c6.text
    assert len(out.clauses) == 10


def test_ids_are_unique_and_sequential():
    out = split_clauses((SAMPLES / "sample_a.txt").read_text(encoding="utf-8"))
    ids = [c.id for c in out.clauses]
    assert ids[0] == "c-01" and ids[-1] == "c-10"
    assert len(set(ids)) == len(ids)


# ---- 형식 변형


def test_title_without_parentheses():
    out = split_clauses("제1조 목적\n내용 가\n제2조 정의\n내용 나\n")
    assert [c.title for c in out.clauses] == ["목적", "정의"]


def test_fullwidth_parentheses_and_spaces():
    out = split_clauses("제 1 조 （목적）\n내용\n제 2 조 （정의）\n내용\n")
    assert [c.no for c in out.clauses] == ["제1조", "제2조"]
    assert [c.title for c in out.clauses] == ["목적", "정의"]


def test_article_with_branch_number():
    out = split_clauses(
        "제1조 (목적)\n가\n제2조 (정의)\n나\n제2조의2 (추가)\n다\n제3조 (기간)\n라\n"
    )
    assert [c.no for c in out.clauses] == ["제1조", "제2조", "제2조의2", "제3조"]
    assert not out.needs_llm


def test_crlf_and_bom():
    out = split_clauses("﻿제1조 (목적)\r\n가\r\n제2조 (정의)\r\n나\r\n")
    assert len(out.clauses) == 2


def test_chapter_lines_are_not_clause_text():
    text = "제1장 총칙\n제1조 (목적)\n가\n제2조 (정의)\n나\n제2장 정산\n제3조 (정산)\n다\n"
    out = split_clauses(text)
    assert [c.no for c in out.clauses] == ["제1조", "제2조", "제3조"]
    assert all("제2장" not in c.text and "제1장" not in c.text for c in out.clauses)


def test_reference_to_article_inside_text_is_not_a_heading():
    text = "제1조 (목적)\n가\n제2조 (정의)\n제1조에 따라 정한다.\n제3조 (기간)\n나\n"
    out = split_clauses(text)
    assert [c.no for c in out.clauses] == ["제1조", "제2조", "제3조"]
    assert "제1조에 따라 정한다." in out.clauses[1].text
    assert not out.needs_llm


def test_preamble_before_first_clause_is_not_a_clause():
    out = split_clauses(
        "웹툰 계약서\n갑과 을은 다음과 같이 계약한다.\n제1조 (목적)\n가\n제2조 (정의)\n나\n"
    )
    assert out.clauses[0].no == "제1조"
    assert "웹툰 계약서" not in out.clauses[0].text


def test_numbered_list_items_inside_numbered_style_are_not_split():
    text = "1. 목적\n가\n2. 지급\n다음과 같다.\n1. 첫째 항목 설명이다.\n2. 둘째 항목 설명이다.\n3. 해지\n나\n"
    out = split_clauses(text)
    assert [c.no for c in out.clauses] == ["1", "2", "3"]


# ---- 규칙이 실패하는 경우 (LLM 보완 대상)


def test_no_headings_needs_llm():
    out = split_clauses("그냥 한 덩어리 글입니다.\n번호도 제목도 없습니다.\n")
    assert out.style == "none" and out.clauses == [] and out.needs_llm


def test_empty_text_needs_llm():
    out = split_clauses("")
    assert out.needs_llm and out.clauses == []


def test_single_heading_is_not_enough():
    assert split_clauses("제1조 (목적)\n가\n").needs_llm


def test_skipped_article_is_flagged():
    # 제3조가 빠져 제4조가 차례를 벗어남: 조항을 놓쳤을 수 있으니 LLM 보완 대상
    out = split_clauses("제1조 (가)\n.\n제2조 (나)\n.\n제4조 (라)\n.\n")
    assert out.needs_llm
    assert any("제4조" in w for w in out.warnings)
    assert [c.no for c in out.clauses] == ["제1조", "제2조"]


def test_first_article_must_start_at_one():
    assert split_clauses("제3조 (가)\n.\n제4조 (나)\n.\n").needs_llm
