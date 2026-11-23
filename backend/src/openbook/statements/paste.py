"""정산서 표 붙여넣기 정규화. 코드만 쓴다 (LLM을 부르지 않는다).

엑셀·웹 표를 복사해 붙여 넣은 글을 StatementDraft로 바꾼다. 하는 일은 '어느 줄이 어느 칸인지'
고르고 숫자 글자를 Decimal로 옮기는 것뿐이다.
- 합계를 새로 계산하지 않는다. 값 줄이 여럿이면 '합계' 줄만 쓴다.
- 단위를 환산하지 않는다. 천원·만원 단위면 넣지 않고 직접 입력을 부탁한다.
- 지급내역형 양식의 칸(매출액, 회사입금액, 정산액, 원천징수, 작가지급액)을 각 칸에 넣는다.
- 애매한 줄(MG 차감, 잔액, 부가세 등)은 넣지 않고 이유(note)를 단다.
경고 문장에는 줄 번호만 쓰고 금액·항목 이름은 넣지 않는다 (로그에 정산서 내용이 남지 않게).

지원 형식
1) 항목-값 줄: "총매출<TAB>1,234,000" / "총매출: 1,234,000원" / "총매출   1,234,000"
2) 머리줄 + 값 줄: 첫 줄이 항목 이름들이고 그 아래 줄이 값 (엑셀 가로 표)
"""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from openbook.schemas.statements import (
    PastedRow,
    StatementDeduction,
    StatementDraft,
    StatementField,
)

MAX_CHARS = 20_000

F = StatementField

# ---------------------------------------------------------------- 항목 이름 분류
# 위에서부터 차례로 본다. 앞 규칙이 뒤 규칙보다 먼저다 (예: '판매 수수료'는 공제, '선인세'는 MG).
_RULES: list[tuple[re.Pattern[str], StatementField | None, str | None]] = [
    (
        re.compile(r"수량|건수|횟수|조회|회차|비율|율$|%"),
        None,
        "금액이 아닌 줄이라 넣지 않았습니다.",
    ),
    (
        re.compile(r"(지급|정산|입금|결제)(예정)?(일|일자|날짜)$"),
        None,
        "날짜 줄이라 넣지 않았습니다.",
    ),
    (
        re.compile(r"MG|선급|선인세|선지급|미니멈|개런티", re.IGNORECASE),
        None,
        "MG·선급금 회수는 계약 조건으로 따로 계산하므로 넣지 않았습니다.",
    ),
    (re.compile(r"잔액|이월"), None, "잔액·이월 줄이라 넣지 않았습니다."),
    (re.compile(r"기간|정산월|대상월|귀속월|해당월"), F.PERIOD, None),
    (
        re.compile(r"부가세|부가가치세|VAT", re.IGNORECASE),
        None,
        "부가세 줄은 대조에 쓰지 않아 넣지 않았습니다.",
    ),
    (re.compile(r"원천|소득세|세액|세금"), F.WITHHOLDING, None),
    (re.compile(r"회사입금|플랫폼입금|순매출|순수익|순판매"), F.NET_REVENUE, None),
    (re.compile(r"정산액|배분|분배|작가수익|작가몫|수익금"), F.SETTLEMENT, None),
    (re.compile(r"수수료|공제|차감|비용|환불"), F.DEDUCTION, None),
    (re.compile(r"지급|정산금|입금"), F.REPORTED_PAYOUT, None),
    (re.compile(r"매출|판매"), F.GROSS, None),
]

# 칸 → StatementDraft 속성. 매출·회사입금액·정산액은 환불이 많은 달에 음수일 수 있다.
_ATTR = {
    F.GROSS: "gross",
    F.NET_REVENUE: "net_revenue",
    F.SETTLEMENT: "reported_settlement",
    F.WITHHOLDING: "reported_withholding",
    F.REPORTED_PAYOUT: "reported_payout",
}
_SIGNED = {F.GROSS, F.NET_REVENUE, F.SETTLEMENT}

_TOTAL = re.compile(r"^(합계|총계|계|소계|total)$", re.IGNORECASE)
_DEDUCTION_TOTAL = re.compile(r"합계|총|소계|계$")


def _key(label: str) -> str:
    """항목 이름 비교용: 괄호 속 단위·공백·콜론을 뺀다."""
    return re.sub(r"\(.*?\)|\[.*?\]|[\s:：]", "", label)


def _classify(label: str) -> tuple[StatementField | None, str | None]:
    """(넣을 칸, 넣지 않는 이유). 모르는 이름이면 (None, None)."""
    k = _key(label)
    if not k:
        return None, None
    for rx, target, note in _RULES:
        if rx.search(k):
            return target, note
    return None, None


def _known(label: str) -> bool:
    return _classify(label) != (None, None)


# ---------------------------------------------------------------- 값 읽기

_AMOUNT = re.compile(
    r"^(?P<neg>[-−△(])?\s*(?:₩|\\|KRW)?\s*"
    r"(?P<num>\d{1,3}(?:,\d{3})+|\d+)(?P<frac>\.\d+)?"
    r"\s*(?:원|KRW)?\s*\)?$",
    re.IGNORECASE,
)
_UNIT_NOT_WON = re.compile(r"(천|만|백만|억)\s*원")
_UNIT_LINE = re.compile(r"단위\s*[:：]?\s*(천|만|백만|억)\s*원")
_DATE = re.compile(r"(\d{4})\s*[-./년]\s*(\d{1,2})(?:\s*[-./월]\s*(\d{1,2}))?")


def _amount(text: str) -> tuple[Decimal, bool] | None:
    """'1,234,000원' -> (Decimal('1234000'), 음수인가). 금액 모양이 아니면 None."""
    m = _AMOUNT.match(text.strip())
    if not m:
        return None
    return Decimal(m["num"].replace(",", "") + (m["frac"] or "")), m["neg"] is not None


def _period(text: str) -> tuple[date, date] | None:
    """'2026-10', '2026년 10월', '2026.10.01 ~ 2026.10.31' -> (시작일, 끝일)."""
    found = list(_DATE.finditer(text))
    try:
        if len(found) == 1 and found[0][3] is None:
            y, mo = int(found[0][1]), int(found[0][2])
            return date(y, mo, 1), date(y, mo, calendar.monthrange(y, mo)[1])
        if len(found) == 2:
            (y1, m1, d1), (y2, m2, d2) = ((int(g[1]), int(g[2]), g[3]) for g in found)
            start = date(y1, m1, int(d1) if d1 else 1)
            end = date(y2, m2, int(d2) if d2 else calendar.monthrange(y2, m2)[1])
            return (start, end) if start <= end else None
    except ValueError:
        return None
    return None


# ---------------------------------------------------------------- 줄 나누기

# 항목 이름에는 숫자가 없다고 본다. 이름 끝 글자로 '('를 받지 않아 "(120,000)" 같은 음수 값을 지킨다.
_LABEL_VALUE = re.compile(r"^(?P<label>[^\d\-−△₩\\]*[^\d\s\-−△(₩\\:：])[\s:：]+(?P<value>\S.*)$")


def _cells(line: str) -> list[str]:
    if "\t" in line:
        cells = [c.strip() for c in line.split("\t")]
    elif re.search(r"\S\s{2,}\S", line):
        cells = [c.strip() for c in re.split(r"\s{2,}", line.strip())]
    elif m := _LABEL_VALUE.match(line.strip()):
        cells = [m["label"], m["value"]]
    else:
        cells = [line.strip()]
    cells = [re.sub(r"[:：]$", "", c).strip() for c in cells]
    while cells and not cells[-1]:
        cells.pop()
    return cells


# ---------------------------------------------------------------- 조립


@dataclass
class _State:
    draft: StatementDraft
    no_amounts: bool  # 단위가 원이 아니면 금액을 하나도 넣지 않는다
    deduction_rows: list[tuple[PastedRow, StatementDeduction, bool]] = field(default_factory=list)


def parse_pasted_statement(text: str) -> StatementDraft:
    """붙여 넣은 정산서 글을 StatementDraft로. 예외를 던지지 않고 경고로 알린다."""
    draft = StatementDraft()
    if len(text) > MAX_CHARS:
        draft.warnings.append(f"붙여 넣은 글이 {MAX_CHARS:,}자를 넘어 읽지 않았습니다.")
        draft.missing = [F.PERIOD, F.GROSS, F.REPORTED_PAYOUT]
        return draft

    lines = [(i, _cells(raw)) for i, raw in enumerate(text.splitlines(), start=1) if raw.strip()]
    st = _State(draft=draft, no_amounts=any(_UNIT_LINE.search(" ".join(c)) for _, c in lines))
    if st.no_amounts:
        draft.warnings.append(
            "금액 단위가 원이 아니어서(천원·만원 등) 금액을 넣지 않았습니다. 직접 입력해 주세요."
        )

    header = next((n for n, (_, c) in enumerate(lines) if _is_header(c)), None)
    if header is None:
        for line_no, cells in lines:
            _take_pair(st, line_no, cells)
    else:
        for line_no, cells in lines[:header]:  # 표 위의 '정산 기간: …' 같은 줄
            _take_pair(st, line_no, cells)
        _take_table(st, lines, header)

    _finish_deductions(st)
    draft.missing = [
        f
        for f, v in (
            (F.PERIOD, draft.period_start),
            (F.GROSS, draft.gross),
            (F.REPORTED_PAYOUT, draft.reported_payout),
        )
        if v is None
    ]
    return draft


def _is_header(cells: list[str]) -> bool:
    """가로 표의 머리줄: 아는 항목 이름이 둘 이상이고 금액 칸이 없다."""
    return (
        len(cells) >= 2
        and sum(_known(c) for c in cells) >= 2
        and not any(_amount(c) or _period(c) for c in cells)
    )


def _take_pair(st: _State, line_no: int, cells: list[str]) -> None:
    label = cells[0]
    rest = [c for c in cells[1:] if c]
    if not rest:
        if _known(label):
            st.draft.rows.append(
                PastedRow(line=line_no, label=label, value="", note="값을 찾지 못했습니다.")
            )
        return  # 제목 줄 등 모르는 한 칸 줄은 건너뛴다
    value = next((c for c in rest if _amount(c)), " ".join(rest))
    _assign(st, PastedRow(line=line_no, label=label, value=value))


def _take_table(st: _State, lines: list[tuple[int, list[str]]], header: int) -> None:
    head_cells = lines[header][1]
    data = [(n, c) for n, c in lines[header + 1 :] if any(c)]
    if len(data) > 1:
        totals = [(n, c) for n, c in data if any(_TOTAL.match(_key(x)) for x in c)]
        if len(totals) != 1:
            st.draft.warnings.append(
                "값 줄이 여러 개라 넣지 않았습니다. 합계 줄을 함께 붙여 넣거나 직접 입력해 주세요."
            )
            return
        data = totals
    if not data:
        st.draft.warnings.append("머리줄 아래에 값 줄이 없습니다.")
        return
    line_no, cells = data[0]
    for col, label in enumerate(head_cells):
        value = cells[col] if col < len(cells) else ""
        if not label or not _known(label):
            continue
        _assign(st, PastedRow(line=line_no, label=label, value=value))


def _assign(st: _State, row: PastedRow) -> None:
    d = st.draft
    d.rows.append(row)
    target, note = _classify(row.label)
    if target is None:
        row.note = note or "어느 칸인지 몰라 넣지 않았습니다."
        return

    if target is F.PERIOD:
        p = _period(row.value)
        if p is None:
            row.note = "기간 형식을 읽지 못했습니다. 예: 2026-10 또는 2026.10.01 ~ 2026.10.31"
        elif d.period_start is not None:
            row.note = "기간으로 보이는 줄이 앞에 있어 넣지 않았습니다."
            d.warnings.append(f"{row.line}번째 줄: 기간이 둘 이상이라 첫 줄만 넣었습니다.")
        else:
            d.period_start, d.period_end = p
            row.field = target
        return

    if st.no_amounts or _UNIT_NOT_WON.search(row.label + row.value):
        row.note = "단위가 원이 아니라 넣지 않았습니다. 직접 입력해 주세요."
        return
    parsed = _amount(row.value)
    if parsed is None:
        row.note = "금액 형식을 읽지 못했습니다."
        return
    amount, negative = parsed

    if target is F.DEDUCTION:
        if negative:
            row.note = "음수로 적힌 공제액을 양수로 넣었습니다."
        is_total = bool(_DEDUCTION_TOTAL.search(_key(row.label)))
        st.deduction_rows.append((row, StatementDeduction(name=row.label, amount=amount), is_total))
        row.field = target
        return

    if negative and target not in _SIGNED:
        row.note = "음수 금액이라 넣지 않았습니다."
        return
    if negative:
        amount = -amount
    attr = _ATTR[target]
    if getattr(d, attr) is not None:
        row.note = "같은 칸으로 보이는 줄이 앞에 있어 넣지 않았습니다."
        d.warnings.append(
            f"{row.line}번째 줄: 같은 칸으로 보이는 줄이 둘 이상이라 첫 줄만 넣었습니다."
        )
        return
    setattr(d, attr, amount)
    row.field = target


def _finish_deductions(st: _State) -> None:
    """개별 공제 줄이 있으면 '공제 합계' 줄은 겹치므로 뺀다. 합계 줄만 있으면 그것을 쓴다."""
    has_items = any(not total for _, _, total in st.deduction_rows)
    for row, ded, total in st.deduction_rows:
        if total and has_items:
            row.field = None
            row.note = "공제 합계 줄은 개별 공제 줄과 겹쳐 넣지 않았습니다."
        else:
            st.draft.deductions.append(ded)
