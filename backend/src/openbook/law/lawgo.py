"""법제처 국가법령정보 공동활용 Open API에서 현행 법령 조문을 받아 LawArticle로 바꾼다.

- 신청: https://open.law.go.kr (기관·개인 신청 후 OC 값을 받는다). 화면 긁기는 쓰지 않는다.
- 환경변수 LAW_OC (필수). 값은 로그·오류에 넣지 않는다.
- 목록: GET {base}/lawSearch.do?OC=..&target=law&type=JSON&query=법령명
- 본문: GET {base}/lawService.do?OC=..&target=law&type=JSON&MST=법령일련번호

응답 모양은 2026-11-24 실제 호출로 확인했다 (저작권법 등 5개 법령, 조문 357개).
항·호·목은 하나면 목록이 아니라 객체로 오므로 parse_law는 둘 다 받는다.
"""

from __future__ import annotations

import os
from datetime import date
from typing import Any

import httpx
from dotenv import load_dotenv

from openbook.law.models import LawArticle

DEFAULT_BASE_URL = "https://www.law.go.kr/DRF"
LAW_PAGE = "https://www.law.go.kr/법령/{name}"


class LawApiError(RuntimeError):
    """법제처 API 호출 실패. 메시지에 OC 값을 넣지 않는다."""


class LawApiClient:
    def __init__(self, oc: str, base_url: str = DEFAULT_BASE_URL, timeout: float = 30.0) -> None:
        if not oc:
            raise ValueError("LAW_OC가 비어 있습니다.")
        self._oc = oc
        self._base = base_url.rstrip("/")
        self._timeout = timeout

    @classmethod
    def from_env(cls) -> LawApiClient:
        load_dotenv()
        return cls(os.environ.get("LAW_OC", ""), os.environ.get("LAW_BASE_URL", DEFAULT_BASE_URL))

    def _get(self, path: str, **params: str) -> dict[str, Any]:
        try:
            resp = httpx.get(
                f"{self._base}/{path}",
                params={"OC": self._oc, "target": "law", "type": "JSON", **params},
                timeout=self._timeout,
            )
        except httpx.HTTPError as exc:
            raise LawApiError(f"법제처 연결 실패 ({type(exc).__name__})") from exc
        if resp.status_code != 200:
            raise LawApiError(f"법제처 호출 실패: HTTP {resp.status_code}")
        try:
            data = resp.json()
        except ValueError as exc:
            raise LawApiError(
                "법제처 응답이 JSON이 아닙니다 (OC 값이나 신청 상태를 확인하세요)."
            ) from exc
        if not isinstance(data, dict):
            raise LawApiError("법제처 응답 형식이 예상과 다릅니다.")
        return data

    def find_current(self, name: str) -> str:
        """법령명이 정확히 같은 현행 법령의 법령일련번호(MST)."""
        data = self._get("lawSearch.do", query=name)
        for row in _as_list(data.get("LawSearch", {}).get("law")):
            if row.get("법령명한글") == name and row.get("현행연혁코드", "현행") == "현행":
                mst = row.get("법령일련번호")
                if mst:
                    return str(mst)
        raise LawApiError(f"현행 법령을 찾지 못했습니다: {name}")

    def articles(self, name: str) -> list[LawArticle]:
        return parse_law(self._get("lawService.do", MST=self.find_current(name)))


def _as_list(x: Any) -> list[Any]:
    if x is None:
        return []
    return x if isinstance(x, list) else [x]


def _text(x: Any) -> str:
    """조문내용 등은 문자열이거나 문자열 목록으로 온다."""
    if isinstance(x, list):
        return "\n".join(_text(i) for i in x if i)
    return str(x).strip() if x else ""


def _date(x: Any) -> date | None:
    s = str(x or "").strip()
    if len(s) == 8 and s.isdigit():
        return date(int(s[:4]), int(s[4:6]), int(s[6:]))
    return None


def _deleted(text: str) -> bool:
    """'제5조 삭제 <2020. 1. 1.>'처럼 삭제 표시만 남은 조문."""
    return len(text) < 40 and "삭제" in text


def parse_law(data: dict[str, Any]) -> list[LawArticle]:
    """lawService.do JSON → 조문 목록. 장·절 제목(조문여부 '전문')과 삭제된 조문은 뺀다."""
    law = data.get("법령") or {}
    info = law.get("기본정보") or {}
    name = _text(info.get("법령명_한글") or info.get("법령명한글"))
    if not name:
        raise LawApiError("법령명이 없는 응답입니다.")
    effective = _date(info.get("시행일자"))

    out: list[LawArticle] = []
    for unit in _as_list((law.get("조문") or {}).get("조문단위")):
        if not isinstance(unit, dict) or unit.get("조문여부", "조문") != "조문":
            continue
        no = str(unit.get("조문번호") or "").strip()
        if not no:
            continue
        branch = str(unit.get("조문가지번호") or "").strip()
        article_no = f"제{no}조" + (f"의{branch}" if branch and branch != "0" else "")

        lines = [_text(unit.get("조문내용"))]
        for para in _as_list(unit.get("항")):
            if not isinstance(para, dict):
                continue
            lines.append(_text(para.get("항내용")))
            for item in _as_list(para.get("호")):
                if not isinstance(item, dict):
                    continue
                lines.append(_text(item.get("호내용")))
                lines.extend(
                    _text(m.get("목내용")) for m in _as_list(item.get("목")) if isinstance(m, dict)
                )
        text = "\n".join(line for line in lines if line)
        if not text or _deleted(text):
            continue
        out.append(
            LawArticle(
                id=f"l-{name}-{article_no}".replace(" ", ""),
                law_name=name,
                article_no=article_no,
                title=_text(unit.get("조문제목")) or None,
                text=text,
                effective_date=_date(unit.get("조문시행일자")) or effective,
                source_url=LAW_PAGE.format(name=name.replace(" ", "")),
            )
        )
    return out
